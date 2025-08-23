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
from sqlalchemy import select, update, insert
from ai.ai import openai_client
from speech.whisper_engine import generate_speech, save_audio_to_file
from text.text import scheduled_lesson_text, homework_reminder_text, buttons_info_text
from text.text import lesson_task_text
from text.text import homework_assigned_text
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
        self.test_interval_minutes = int(os.getenv("TEST_INTERVAL_MINUTES", "5"))
        
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
                        # Отправляем второе сообщение с заданием по теме урока
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

    # Закрепление материала
    async def send_reinforcement_question(self, session=None):
        """
        Отправляет вопрос на закрепление материала, пройденного сегодня
        """
        try:
            print(f"🔍 Отправка вопроса на закрепление в {datetime.now()}")
            
            # Используем переданную сессию или создаем новую
            should_close_session = False
            if session is None:
                session = session_maker()
                should_close_session = True
            
            try:
                # Получаем всех активных пользователей
                result = await session.execute(
                    select(User).where(User.id.isnot(None))
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Проверяем время последнего сообщения пользователя
                        # Получаем последние сообщения пользователя
                        last_messages_result = await session.execute(
                            select(MessageHistory)
                            .where(MessageHistory.user_id == user.id)
                            .order_by(MessageHistory.timestamp.desc())
                            .limit(5)  # Увеличиваем лимит для лучшей проверки
                        )
                        last_messages = last_messages_result.scalars().all()
                        
                        if last_messages:
                            last_message = last_messages[0]
                            time_diff = datetime.now() - last_message.timestamp
                            
                            # Проверяем, было ли последнее сообщение от пользователя ответом на вопрос закрепления
                            is_reinforcement_response = False
                            if (last_message.role == 'user' and len(last_messages) > 1):
                                # Проверяем предыдущее сообщение от бота
                                prev_message = last_messages[1]
                                if (prev_message.role == 'bot' and 
                                    '💭 Вопрос на закрепление материала:' in prev_message.content):
                                    is_reinforcement_response = True
                            
                            # Проверяем, не отправляли ли мы уже вопрос закрепления недавно
                            recent_reinforcement_question = False
                            for msg in last_messages:
                                if (msg.role == 'bot' and 
                                    '💭 Вопрос на закрепление материала:' in msg.content):
                                    # Если вопрос был отправлен менее 2 минут назад, пропускаем
                                    msg_time_diff = datetime.now() - msg.timestamp
                                    if msg_time_diff.total_seconds() < 120:  # 2 минуты
                                        recent_reinforcement_question = True
                                        break
                            
                            # Если последнее сообщение было менее TEST_INTERVAL_MINUTES назад И это не ответ на закрепление, пропускаем пользователя
                            if (time_diff.total_seconds() < self.test_interval_minutes * 60 and 
                                not is_reinforcement_response):
                                print(f"⏭️ Пользователь {user.id} недавно общался (последнее сообщение {time_diff.total_seconds():.0f} сек назад)")
                                continue
                            
                            # Если недавно отправляли вопрос закрепления, пропускаем
                            if recent_reinforcement_question:
                                print(f"⏭️ Пользователю {user.id} недавно отправляли вопрос закрепления")
                                continue
                        
                        # Получаем тему, которую пользователь изучал сегодня
                        today_topic = await self._get_today_topic_for_user(session, user)
                        
                        # Если нет темы за сегодня, используем текущую тему пользователя
                        if not today_topic and user.current_topic_id:
                            topic_result = await session.execute(
                                select(Topic).where(Topic.id == user.current_topic_id)
                            )
                            today_topic = topic_result.scalar_one_or_none()
                        
                        # Если все еще нет темы, используем первую доступную тему
                        if not today_topic:
                            all_topics_result = await session.execute(
                                select(Topic).order_by(Topic.id).limit(1)
                            )
                            today_topic = all_topics_result.scalar_one_or_none()
                        
                        if today_topic:
                            # Получаем предыдущие вопросы для исключения повторений
                            previous_questions = await self._get_previous_reinforcement_questions(session, user.id)
                            
                            # Генерируем вопрос на закрепление
                            try:
                                question = await openai_client.generate_reinforcement_question(
                                    topic_title=today_topic.title,
                                    topic_description=today_topic.description,
                                    previous_questions=previous_questions
                                )
                            except Exception as e:
                                print(f"❌ Ошибка при генерации вопроса через OpenAI: {e}")
                                # Отправляем сообщение об ошибке
                                await self.bot.send_message(
                                    chat_id=user.id,
                                    text="❌ Извините, произошла ошибка при генерации вопроса. Попробуйте позже."
                                )
                                continue
                            
                            # Отправляем вопрос
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=f"💭 Вопрос на закрепление материала:\n\n{question}\n\nОтправьте текстовый ответ!")
                            
                            # Сохраняем вопрос в message_history для отслеживания
                            await session.execute(
                                insert(MessageHistory).values(
                                    user_id=user.id,
                                    role='bot',
                                    content=f"💭 Вопрос на закрепление материала:\n\n{question}\n\nОтправьте текстовый ответ!",
                                    timestamp=datetime.now()
                                )
                            )
                            await session.commit()
                            
                            print(f"✅ Вопрос на закрепление отправлен пользователю {user.id}")
                        else:
                            # Если нет тем вообще, отправляем общий вопрос
                            general_questions = [
                                "What do you like to do in your free time?",
                                "How do you spend your weekends?",
                                "What is your favorite hobby?",
                                "Describe your best friend in one sentence.",
                                "What makes you happy?",
                                "How do you relax after a busy day?",
                                "What is your biggest dream?",
                                "How do you help others?"
                            ]
                            
                            import random
                            question = random.choice(general_questions)
                            
                            # Отправляем общий вопрос
                            await self.bot.send_message(
                                chat_id=user.id,
                                text=f"💭 Вопрос на закрепление материала:\n\n{question}\n\nОтправьте текстовый ответ!")
                            
                            # Сохраняем вопрос в message_history для отслеживания
                            await session.execute(
                                insert(MessageHistory).values(
                                    user_id=user.id,
                                    role='bot',
                                    content=f"💭 Вопрос на закрепление материала:\n\n{question}\n\nОтправьте текстовый ответ!",
                                    timestamp=datetime.now()
                                )
                            )
                            await session.commit()
                            
                            print(f"✅ Общий вопрос на закрепление отправлен пользователю {user.id}")
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки вопроса пользователю {user.id}: {e}")
                        
            finally:
                # Закрываем сессию только если мы её создавали
                if should_close_session:
                    await session.close()
                        
        except Exception as e:
            print(f"❌ Ошибка в send_reinforcement_question: {e}")

    async def _get_previous_reinforcement_questions(self, session, user_id: int):
        """
        Получает предыдущие вопросы закрепления для исключения повторений
        """
        try:
            # Получаем последние вопросы закрепления для пользователя
            recent_questions_result = await session.execute(
                select(MessageHistory)
                .where(
                    MessageHistory.user_id == user_id,
                    MessageHistory.role == 'bot',
                    MessageHistory.content.like('%💭 Вопрос на закрепление материала:%')
                )
                .order_by(MessageHistory.timestamp.desc())
                .limit(5)  # Получаем последние 5 вопросов
            )
            recent_questions = recent_questions_result.scalars().all()
            
            # Извлекаем текст предыдущих вопросов
            previous_questions = []
            for msg in recent_questions:
                # Извлекаем вопрос из сообщения (убираем префикс)
                content = msg.content
                if '💭 Вопрос на закрепление материала:' in content:
                    question_start = content.find('\n\n') + 2
                    question_end = content.find('\n\nОтправьте')
                    if question_start > 1 and question_end > question_start:
                        question = content[question_start:question_end].strip()
                        previous_questions.append(question)
            
            return previous_questions
            
        except Exception as e:
            print(f"Ошибка при получении предыдущих вопросов: {e}")
            return []

    async def handle_reinforcement_answer(self, user_id: int, answer_text: str, session=None):
        """
        Обрабатывает ответ пользователя на вопрос закрепления материала
        """
        try:
            print(f"📝 Обработка ответа на закрепление от пользователя {user_id}")
            print(f"📝 Ответ пользователя: {answer_text}")
            
            # Используем переданную сессию или создаем новую
            should_close_session = False
            if session is None:
                session = session_maker()
                should_close_session = True
            
            try:
                # Получаем пользователя
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    print(f"❌ Пользователь {user_id} не найден")
                    return
                
                print(f"📝 Пользователь найден: {user.id}")
                
                # Получаем текущую тему
                current_topic = None
                if user.current_topic_id:
                    topic_result = await session.execute(
                        select(Topic).where(Topic.id == user.current_topic_id)
                    )
                    current_topic = topic_result.scalar_one_or_none()
                
                if current_topic:
                    print(f"📝 Текущая тема: {current_topic.title}")
                    
                    # Получаем историю диалога для правильной проверки ответа
                    conversation_history = []
                    try:
                        # Получаем последние сообщения пользователя для контекста
                        history_result = await session.execute(
                            select(MessageHistory)
                            .where(MessageHistory.user_id == user_id)
                            .order_by(MessageHistory.timestamp.desc())
                            .limit(10)  # Последние 10 сообщений
                        )
                        recent_messages = history_result.scalars().all()
                        
                        # Формируем историю диалога в правильном формате
                        for msg in reversed(recent_messages):  # В хронологическом порядке
                            conversation_history.append({
                                "role": msg.role,
                                "content": msg.content
                            })
                        
                        print(f"📝 История диалога получена: {len(conversation_history)} сообщений")
                    except Exception as e:
                        print(f"📝 Ошибка при получении истории диалога: {e}")
                        conversation_history = []
                    
                    try:
                        print(f"📝 Генерируем обратную связь через OpenAI...")
                        
                        # Используем check_pronunciation_and_answer для генерации feedback
                        feedback_result = await openai_client.check_pronunciation_and_answer(
                            user_answer=answer_text,
                            current_topic={
                                "title": str(current_topic.title),
                                "description": str(current_topic.description),
                                "tasks": json.loads(str(current_topic.tasks)) if current_topic.tasks else []
                            },
                            context="Reinforcement question response",
                            conversation_history=conversation_history
                        )
                        
                        print(f"📝 Feedback получен: {feedback_result}")
                        
                        # Формируем ответ с обратной связью
                        response_text = f"💡 Обратная связь по закреплению материала:\n\n{feedback_result.get('feedback', '')}\n\n"
                        if not feedback_result.get('is_correct', True):
                            response_text += f"Правильный ответ: {feedback_result.get('correct_answer', '')}\n\n"
                            response_text += f"Объяснение: {feedback_result.get('explanation', '')}\n\n"
                        
                        print(f"📝 Отправляем обратную связь пользователю {user_id}")
                        # Отправляем обратную связь
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=response_text
                        )
                        
                        print(f"📝 Сохраняем обратную связь в базу данных...")
                        # Сохраняем только обратную связь (ответ пользователя уже сохранен в handle_reinforcement_response)
                        await session.execute(
                            insert(MessageHistory).values(
                                user_id=user_id,
                                role='bot',
                                content=response_text,
                                timestamp=datetime.now()
                            )
                        )
                        
                        await session.commit()
                        
                        print(f"✅ Обратная связь отправлена пользователю {user_id}")
                        
                    except Exception as e:
                        print(f"❌ Ошибка при генерации обратной связи через OpenAI: {e}")
                        # Отправляем сообщение об ошибке
                        await self.bot.send_message(
                            chat_id=user_id,
                            text="❌ Извините, произошла ошибка при обработке ответа. Попробуйте позже."
                        )
                        
                        # Сохраняем ошибку в базу данных (ответ пользователя уже сохранен)
                        await session.execute(
                            insert(MessageHistory).values(
                                user_id=user_id,
                                role='bot',
                                content="❌ Ошибка при обработке ответа",
                                timestamp=datetime.now()
                            )
                        )
                        
                        await session.commit()
                else:
                    print(f"📝 Текущая тема не найдена для пользователя {user_id}")
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="Спасибо за ответ! Продолжайте изучать английский! 🌟"
                    )
                    
            finally:
                # Закрываем сессию только если мы её создавали
                if should_close_session:
                    await session.close()
                    
        except Exception as e:
            print(f"❌ Ошибка обработки ответа на закрепление: {e}")

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

# Глобальный экземпляр планировщика
lesson_scheduler: Optional[LessonScheduler] = None 