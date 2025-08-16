import asyncio
import os
import json
from datetime import datetime, time
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from aiogram.types import FSInputFile
from database.engine import session_maker
from database.models import User, Topic
from sqlalchemy import select
from ai.ai import openai_client
from speech.whisper_engine import generate_speech, save_audio_to_file
from text.text import scheduled_lesson_text, homework_reminder_text

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
            # Добавляем задачу для тестового режима (каждые N минут)
            self.scheduler.add_job(
                self.send_lesson_reminder,
                'interval',
                minutes=self.test_interval_minutes,
                id="test_lesson",
                name=f"Тестовый урок каждые {self.test_interval_minutes} минут",
                replace_existing=True
            )
        else:
            print(f"⏰ Время урока: {self.lesson_time} ({self.timezone})")
            # Добавляем задачу для ежедневного урока
            self.scheduler.add_job(
                self.send_lesson_reminder,
                CronTrigger(hour=self.lesson_time_obj.hour, minute=self.lesson_time_obj.minute, timezone=self.timezone),
                id="daily_lesson",
                name="Ежедневный урок английского",
                replace_existing=True
            )
            
            # Добавляем задачу для напоминания о домашнем задании (через 2 часа после урока)
            reminder_hour = (self.lesson_time_obj.hour + 2) % 24
            self.scheduler.add_job(
                self.send_homework_reminder,
                CronTrigger(hour=reminder_hour, minute=self.lesson_time_obj.minute, timezone=self.timezone),
                id="homework_reminder",
                name="Напоминание о домашнем задании",
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
                        
                        print(f"✅ Напоминание отправлено пользователю {user.id}")
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки пользователю {user.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка в send_lesson_reminder: {e}")
    
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


    async def send_homework_reminder(self):
        """
        Отправляет напоминание о домашнем задании
        """
        try:
            print(f"📝 Отправка напоминания о домашнем задании в {datetime.now()}")
            
            # Получаем всех активных пользователей
            async with session_maker() as session:
                result = await session.execute(
                    select(User).where(User.id.isnot(None))
                )
                users = result.scalars().all()
                
                for user in users:
                    try:
                        # Отправляем текстовое сообщение (для домашнего задания достаточно текста)
                        await self.bot.send_message(
                            chat_id=user.id,
                            text=homework_reminder_text
                        )
                        print(f"✅ Напоминание о ДЗ отправлено пользователю {user.id}")
                        
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки пользователю {user.id}: {e}")
                        
        except Exception as e:
            print(f"❌ Ошибка в send_homework_reminder: {e}")


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