import asyncio
import os
import json
from datetime import datetime, time, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from aiogram.types import FSInputFile
from database.engine import session_maker
from database.models import User, Topic, MessageHistory
from sqlalchemy import select, update
from ai.ai import openai_client
from speech.whisper_engine import generate_speech, save_audio_to_file
from text.text import scheduled_lesson_text, homework_reminder_text, buttons_info_text
from kbds.inline import get_lesson_buttons_keyboard

load_dotenv()

class LessonScheduler:
    """
    Планировщик для автоматических уроков английского языка
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
        # Получаем настройки из переменных окружения
        self.timezone = os.getenv("TIMEZONE", "Asia/Shanghai")  # UTC+8
        self.lesson_time = os.getenv("LESSON_TIME", "12:00")
        self.group_id = os.getenv("GROUP_ID")
        
        # Настройки для тестирования (каждые 10 минут)
        self.test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        self.test_interval_minutes = int(os.getenv("TEST_INTERVAL_MINUTES", "960"))
        
        # Парсим время урока
        hour, minute = map(int, self.lesson_time.split(":"))
        self.lesson_time_obj = time(hour, minute)
    
    async def start(self):
        """
        Запускает планировщик
        """
        print(f"🚀 Запуск планировщика уроков...")
        
        if self.test_mode:
            print(f"🧪 ТЕСТОВЫЙ РЕЖИМ: каждые {self.test_interval_minutes} минут")
            # Добавляем только задачу для закрепления материала (каждые N минут)
            # Убираем send_lesson_reminder из тестового режима - он будет только раз в неделю
            self.scheduler.add_job(
                self.send_reinforcement_question,
                'interval',
                minutes=self.test_interval_minutes,
                id="reinforcement_question",
                name=f"Вопрос на закрепление каждые {self.test_interval_minutes} минут",
                replace_existing=True
            )
        else:
            print(f"⏰ Время урока: {self.lesson_time} ({self.timezone})")
            
            # Добавляем задачу для ежедневного урока (понедельник-пятница)
            self.scheduler.add_job(
                self.send_lesson_reminder,
                CronTrigger(
                    day_of_week='mon-fri',
                    hour=self.lesson_time_obj.hour, 
                    minute=self.lesson_time_obj.minute, 
                    timezone=self.timezone
                ),
                id="daily_lesson",
                name="Ежедневный урок английского (пн-пт)",
                replace_existing=True
            )
            
            # Добавляем задачу для закрепления материала (каждые N минут)
            self.scheduler.add_job(
                self.send_reinforcement_question,
                'interval',
                minutes=self.test_interval_minutes,
                id="reinforcement_question",
                name=f"Вопрос на закрепление каждые {self.test_interval_minutes} минут",
                replace_existing=True
            )
            
            # Добавляем задачу для еженедельного домашнего задания (пятница 18:00)
            self.scheduler.add_job(
                self.send_weekly_homework,
                CronTrigger(
                    day_of_week='fri',
                    hour=18, 
                    minute=0, 
                    timezone=self.timezone
                ),
                id="weekly_homework",
                name="Еженедельное домашнее задание (пятница 18:00)",
                replace_existing=True
            )
            
            # Добавляем задачу для перехода к новой теме (понедельник 12:00)
            self.scheduler.add_job(
                self.start_new_week_topic,
                CronTrigger(
                    day_of_week='mon',
                    hour=12, 
                    minute=0, 
                    timezone=self.timezone
                ),
                id="new_week_topic",
                name="Переход к новой теме (понедельник 12:00)",
                replace_existing=True
            )
        
        # Запускаем планировщик
        self.scheduler.start()
        print("✅ Планировщик запущен!")
    
    async def stop(self):
        """
        Останавливает планировщик
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("🛑 Планировщик остановлен!")
    
    async def send_lesson_reminder(self):
        """
        Отправляет напоминание о начале урока с голосовым сообщением
        """
        try:
            print(f"📚 Отправка напоминания о уроке в {datetime.now()}")
            
            # Получаем всех активных пользователей
            async with session_maker() as session:
                result = await session.execute(
                    select(User).where(User.id.isnot(None))
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Проверяем, не находится ли пользователь в активном диалоге
                        # Получаем последние сообщения пользователя
                        last_messages_result = await session.execute(
                            select(MessageHistory)
                            .where(MessageHistory.user_id == user.id)
                            .order_by(MessageHistory.timestamp.desc())
                            .limit(3)  # Получаем последние 3 сообщения
                        )
                        last_messages = last_messages_result.scalars().all()
                        
                        if last_messages:
                            last_message = last_messages[0]
                            time_diff = datetime.now() - last_message.timestamp
                            
                            # Проверяем, есть ли завершающее сообщение от бота
                            has_ending_message = False
                            for msg in last_messages:
                                if (msg.role == 'bot' and 
                                    any(phrase in msg.content.lower() for phrase in [
                                        'пора закончить разговор',
                                        'кажется, пора закончить',
                                        'закончить разговор',
                                        'всегда можешь вернуться',
                                        '🏁'
                                    ])):
                                    has_ending_message = True
                                    break
                            
                            # Если последнее сообщение было менее 10 минут назад И нет завершающего сообщения, пропускаем пользователя
                            if time_diff.total_seconds() < 600 and not has_ending_message:  # 10 минут = 600 секунд
                                print(f"⏭️ Пользователь {user.id} находится в активном диалоге (последнее сообщение {time_diff.total_seconds():.0f} сек назад)")
                                continue
                        
                        # Получаем следующую тему для пользователя
                        next_topic = await self._get_next_topic_for_user(session, user)
                        
                        if next_topic:
                            # Генерируем персонализированное сообщение через OpenAI
                            try:
                                lesson_text = await openai_client.generate_lesson_start_message(
                                    topic_title=next_topic.title,
                                    topic_description=next_topic.description
                                )
                            except Exception as e:
                                print(f"Ошибка при генерации сообщения через OpenAI: {e}")
                                # Fallback сообщение
                                lesson_text = f"Hello! 👋 My name is Marcus. Ready to learn about {next_topic.title}? Let's start our English lesson! (Привет! Готов изучать тему '{next_topic.title}'? Начинаем урок английского!)"
                            
                            # Генерируем задание для урока
                            try:
                                topic_tasks = json.loads(next_topic.tasks) if next_topic.tasks else []
                                task_text = await openai_client.generate_lesson_task(
                                    topic_title=next_topic.title,
                                    topic_description=next_topic.description,
                                    topic_tasks=topic_tasks
                                )
                            except Exception as e:
                                print(f"Ошибка при генерации задания через OpenAI: {e}")
                                # Fallback задание
                                if topic_tasks and len(topic_tasks) > 0:
                                    task_text = topic_tasks[0]
                                else:
                                    task_text = f"Расскажи о теме '{next_topic.title}' на английском языке"
                            
                            # Устанавливаем тему как текущую для пользователя
                            user.current_topic_id = next_topic.id
                            await session.commit()
                        else:
                            # Если все темы пройдены
                            lesson_text = "🎉 Congratulations! You've completed all topics! You're doing great! (Поздравляю! Вы изучили все темы! Вы отлично справляетесь!)"
                        
                        try:
                            audio_bytes = await generate_speech(lesson_text)
                            if audio_bytes:
                                # Сохраняем аудио в файл
                                audio_path = await save_audio_to_file(audio_bytes, f"lesson_reminder_{user.id}.mp3")
                                if audio_path:
                                    # Отправляем голосовое сообщение
                                    await self.bot.send_voice(
                                        chat_id=user.id,
                                        voice=FSInputFile(audio_path),
                                        caption=lesson_text
                                    )
                                    # Удаляем временный файл
                                    try:
                                        os.unlink(audio_path)
                                    except:
                                        pass
                                else:
                                    # Если не удалось сохранить аудио, отправляем только текст
                                    await self.bot.send_message(
                                        chat_id=user.id,
                                        text=lesson_text
                                    )
                            else:
                                # Если не удалось сгенерировать аудио, отправляем только текст
                                await self.bot.send_message(
                                    chat_id=user.id,
                                    text=lesson_text
                                )
                        except Exception as e:
                            print(f"Ошибка при генерации голосового сообщения для пользователя {user.id}: {e}")
                            # Fallback на текстовое сообщение
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=lesson_text
                            )
                        
                        # Отправляем второе сообщение с заданием
                        from text.text import lesson_task_text
                        if next_topic:
                            task_message = lesson_task_text.format(task_text=task_text)
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=task_message
                            )
                        
                        print(f"✅ Напоминание отправлено пользователю {user.id}")
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки пользователю {user.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка в send_lesson_reminder: {e}")

    async def send_reinforcement_question(self):
        """
        Отправляет вопрос на закрепление материала, пройденного сегодня
        """
        try:
            print(f"🔍 Отправка вопроса на закрепление в {datetime.now()}")
            
            # Получаем всех активных пользователей
            async with session_maker() as session:
                result = await session.execute(
                    select(User).where(User.id.isnot(None))
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Проверяем, не находится ли пользователь в активном диалоге
                        # Получаем последние сообщения пользователя
                        last_messages_result = await session.execute(
                            select(MessageHistory)
                            .where(MessageHistory.user_id == user.id)
                            .order_by(MessageHistory.timestamp.desc())
                            .limit(3)  # Получаем последние 3 сообщения
                        )
                        last_messages = last_messages_result.scalars().all()
                        
                        if last_messages:
                            last_message = last_messages[0]
                            time_diff = datetime.now() - last_message.timestamp
                            
                            # Проверяем, есть ли завершающее сообщение от бота
                            has_ending_message = False
                            for msg in last_messages:
                                if (msg.role == 'bot' and 
                                    any(phrase in msg.content.lower() for phrase in [
                                        'пора закончить разговор',
                                        'кажется, пора закончить',
                                        'закончить разговор',
                                        'всегда можешь вернуться',
                                        '🏁'
                                    ])):
                                    has_ending_message = True
                                    break
                            
                            # Если последнее сообщение было менее 10 минут назад И нет завершающего сообщения, пропускаем пользователя
                            if time_diff.total_seconds() < 600 and not has_ending_message:  # 10 минут = 600 секунд
                                print(f"⏭️ Пользователь {user.id} находится в активном диалоге (последнее сообщение {time_diff.total_seconds():.0f} сек назад)")
                                continue
                        
                        # Получаем тему, которую пользователь изучал сегодня
                        today_topic = await self._get_today_topic_for_user(session, user)
                        
                        if today_topic:
                            # Генерируем простой вопрос на закрепление
                            try:
                                question = await self._generate_reinforcement_question(today_topic)
                            except Exception as e:
                                print(f"Ошибка при генерации вопроса через OpenAI: {e}")
                                # Fallback вопрос
                                question = f"What do you think about {today_topic.title}?"
                            
                            # Отправляем вопрос
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=f"💭 Вопрос на закрепление материала:\n\n{question}\n\nОтправьте текстовый ответ!")
                            
                            print(f"✅ Вопрос на закрепление отправлен пользователю {user.id}")
                        else:
                            # Если пользователь не изучал тему сегодня, пропускаем
                            print(f"⏭️ Пользователь {user.id} не изучал тему сегодня")
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки вопроса пользователю {user.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка в send_reinforcement_question: {e}")

    async def send_weekly_homework(self):
        """
        Отправляет еженедельное домашнее задание (пятница)
        """
        try:
            print(f"📝 Отправка еженедельного домашнего задания в {datetime.now()}")
            
            # Получаем всех активных пользователей
            async with session_maker() as session:
                result = await session.execute(
                    select(User).where(User.id.isnot(None))
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Получаем тему, которую пользователь изучал на этой неделе
                        weekly_topic = await self._get_weekly_topic_for_user(session, user)
                        
                        if weekly_topic:
                            # Генерируем домашнее задание
                            try:
                                homework_text = await openai_client.generate_homework(
                                    current_topic={
                                        "title": weekly_topic.title,
                                        "description": weekly_topic.description,
                                        "tasks": json.loads(weekly_topic.tasks) if weekly_topic.tasks else []
                                    },
                                    conversation_history=[]  # Пустая история для еженедельного ДЗ
                                )
                            except Exception as e:
                                print(f"Ошибка при генерации домашнего задания через OpenAI: {e}")
                                # Fallback домашнее задание
                                homework_text = f"Напишите небольшое эссе (5-7 предложений) на тему '{weekly_topic.title}'. Используйте изученные слова и грамматические конструкции."
                            
                            # Отправляем домашнее задание
                            from text.text import homework_assigned_text
                            homework_message = homework_assigned_text.format(homework_text=homework_text)
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=homework_message
                            )
                            
                            print(f"✅ Еженедельное домашнее задание отправлено пользователю {user.id}")
                        else:
                            # Если пользователь не изучал тему на этой неделе
                            await self.bot.send_message(
                                chat_id=user.id,
                                text="📚 На этой неделе вы не изучали новые темы. Отдохните и подготовьтесь к следующей неделе! 😊"
                            )
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки домашнего задания пользователю {user.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка в send_weekly_homework: {e}")

    async def start_new_week_topic(self):
        """
        Переходит к новой теме в начале недели (понедельник)
        """
        try:
            print(f"🔄 Переход к новой теме в {datetime.now()}")
            
            # Получаем всех активных пользователей
            async with session_maker() as session:
                result = await session.execute(
                    select(User).where(User.id.isnot(None))
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Получаем следующую тему для пользователя
                        next_topic = await self._get_next_topic_for_user(session, user)
                        
                        if next_topic:
                            # Устанавливаем новую тему как текущую
                            await session.execute(
                                update(User)
                                .where(User.id == user.id)
                                .values(current_topic_id=next_topic.id)
                            )
                            await session.commit()
                            
                            # Отправляем сообщение о новой теме
                            message = f"🎯 Новая неделя - новая тема! На этой неделе мы будем изучать: **{next_topic.title}**\n\n{next_topic.description}\n\nГотовы начать? Отправьте голосовое сообщение!"
                            
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=message
                            )
                            
                            print(f"✅ Новая тема установлена для пользователя {user.id}: {next_topic.title}")
                        else:
                            # Если все темы пройдены
                            await self.bot.send_message(
                                chat_id=user.id,
                                text="🎉 Поздравляю! Вы изучили все доступные темы! Вы отлично справляетесь! 😊"
                            )
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка установки новой темы для пользователя {user.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка в start_new_week_topic: {e}")

    async def _get_next_topic_for_user(self, session, user):
        """
        Получает следующую непройденную тему для пользователя
        """
        try:
            # Получаем список пройденных тем
            progress_str = str(user.progress) if user.progress else "[]"
            completed_topics = json.loads(progress_str)
            
            # Ищем непройденную тему
            result = await session.execute(
                select(Topic)
                .where(Topic.id.notin_(completed_topics))
                .order_by(Topic.id)
                .limit(1)
            )
            
            return result.scalar_one_or_none()
            
        except Exception as e:
            print(f"Ошибка при получении следующей темы для пользователя {user.id}: {e}")
            return None

    async def _get_today_topic_for_user(self, session, user):
        """
        Получает тему, которую пользователь изучал сегодня
        """
        try:
            # Получаем сообщения пользователя за сегодня
            today = datetime.now().date()
            result = await session.execute(
                select(MessageHistory)
                .where(
                    MessageHistory.user_id == user.id,
                    MessageHistory.timestamp >= today
                )
                .order_by(MessageHistory.timestamp.desc())
                .limit(10)
            )
            
            today_messages = result.scalars().all()
            
            if today_messages:
                # Если есть сообщения за сегодня, возвращаем текущую тему
                if user.current_topic_id:
                    topic_result = await session.execute(
                        select(Topic).where(Topic.id == user.current_topic_id)
                    )
                    return topic_result.scalar_one_or_none()
            
            return None
            
        except Exception as e:
            print(f"Ошибка при получении темы за сегодня для пользователя {user.id}: {e}")
            return None

    async def _get_weekly_topic_for_user(self, session, user):
        """
        Получает тему, которую пользователь изучал на этой неделе
        """
        try:
            # Получаем начало недели (понедельник)
            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            
            # Получаем сообщения пользователя за эту неделю
            result = await session.execute(
                select(MessageHistory)
                .where(
                    MessageHistory.user_id == user.id,
                    MessageHistory.timestamp >= start_of_week
                )
                .order_by(MessageHistory.timestamp.desc())
                .limit(20)
            )
            
            weekly_messages = result.scalars().all()
            
            if weekly_messages:
                # Если есть сообщения за неделю, возвращаем текущую тему
                if user.current_topic_id:
                    topic_result = await session.execute(
                        select(Topic).where(Topic.id == user.current_topic_id)
                    )
                    return topic_result.scalar_one_or_none()
            
            return None
            
        except Exception as e:
            print(f"Ошибка при получении темы за неделю для пользователя {user.id}: {e}")
            return None

    async def _generate_reinforcement_question(self, topic):
        """
        Генерирует простой вопрос на закрепление материала
        """
        try:
            system_prompt = """
            Ты - учитель английского языка Marcus. Создай простой вопрос на закрепление материала.
            
            Вопрос должен быть:
            - Простым и понятным
            - На английском языке
            - Соответствующим теме урока
            - Выполнимым в 1-2 предложения
            - Мотивирующим к размышлению
            
            Примеры вопросов:
            - "What do you usually eat for breakfast?"
            - "How do you spend your weekends?"
            - "What is your favorite hobby?"
            - "Describe your best friend in one sentence."
            """
            
            user_prompt = f"""
            Создай простой вопрос на закрепление материала по теме: "{topic.title}"
            
            Описание темы: {topic.description}
            
            Вопрос должен быть простым и мотивировать ученика к размышлению.
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await openai_client.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=50,
                temperature=0.7,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Ошибка при генерации вопроса на закрепление: {e}")
            return f"What do you think about {topic.title}?"

    async def send_test_message(self, user_id: int):
        """
        Отправляет тестовое сообщение пользователю
        """
        try:
            # Генерируем тестовое голосовое сообщение
            test_text = "🧪 Hello! This is a test message from the lesson scheduler. Everything is working correctly!"
            
            try:
                audio_bytes = await generate_speech(test_text)
                if audio_bytes:
                    # Сохраняем аудио в файл
                    audio_path = await save_audio_to_file(audio_bytes, f"test_message_{user_id}.mp3")
                    if audio_path:
                        # Отправляем голосовое сообщение
                        await self.bot.send_voice(
                            chat_id=user_id,
                            voice=FSInputFile(audio_path),
                            caption=test_text
                        )
                        # Удаляем временный файл
                        try:
                            os.unlink(audio_path)
                        except:
                            pass
                    else:
                        # Если не удалось сохранить аудио, отправляем только текст
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=test_text
                        )
                else:
                    # Если не удалось сгенерировать аудио, отправляем только текст
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=test_text
                    )
            except Exception as e:
                print(f"Ошибка при генерации тестового голосового сообщения: {e}")
                # Fallback на текстовое сообщение
                await self.bot.send_message(
                    chat_id=user_id,
                    text=test_text
                )
            
            print(f"✅ Тестовое сообщение отправлено пользователю {user_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки тестового сообщения: {e}")

# Глобальный экземпляр планировщика
lesson_scheduler: Optional[LessonScheduler] = None 