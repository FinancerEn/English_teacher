#!/usr/bin/env python3
"""
Скрипт для просмотра содержимого базы данных English Tutor Bot
"""

import asyncio
import json
from database.engine import session_maker
from database.models import Topic, User, MessageHistory, Homework
from sqlalchemy import select

async def view_database():
    """Просмотр содержимого базы данных"""
    
    async with session_maker() as session:
        print("=" * 60)
        print("📚 СОДЕРЖИМОЕ БАЗЫ ДАННЫХ ENGLISH TUTOR BOT")
        print("=" * 60)
        
        # 1. Темы уроков
        print("\n🎯 ТЕМЫ УРОКОВ:")
        print("-" * 30)
        result = await session.execute(select(Topic))
        topics = result.scalars().all()
        
        if not topics:
            print("❌ Темы не найдены! Запустите: python database/load_topics.py")
        else:
            for i, topic in enumerate(topics, 1):
                print(f"\n{i}. {topic.title}")
                print(f"   Описание: {topic.description}")
                tasks = json.loads(topic.tasks) if topic.tasks else []
                print(f"   Задания: {', '.join(tasks)}")
                print(f"   Статус: {'✅ Завершена' if topic.is_completed else '⏳ В процессе'}")
        
        # 2. Пользователи
        print("\n\n👥 ПОЛЬЗОВАТЕЛИ:")
        print("-" * 30)
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("❌ Пользователи не найдены")
        else:
            for user in users:
                print(f"\nID: {user.id}")
                print(f"   Текущая тема: {user.current_topic_id or 'Не выбрана'}")
                print(f"   Последний урок: {user.last_lesson_date or 'Нет'}")
                progress = json.loads(user.progress) if user.progress else []
                print(f"   Пройденные темы: {len(progress)} из {len(topics)}")
                print(f"   Создан: {user.created_at}")
        
        # 3. История сообщений (последние 10)
        print("\n\n💬 ПОСЛЕДНИЕ СООБЩЕНИЯ:")
        print("-" * 30)
        result = await session.execute(
            select(MessageHistory)
            .order_by(MessageHistory.timestamp.desc())
            .limit(10)
        )
        messages = result.scalars().all()
        
        if not messages:
            print("❌ Сообщения не найдены")
        else:
            for msg in messages:
                role_emoji = "👤" if msg.role == "user" else "🤖"
                print(f"{role_emoji} [{msg.timestamp}] {msg.content[:50]}...")
        
        # 4. Домашние задания
        print("\n\n📝 ДОМАШНИЕ ЗАДАНИЯ:")
        print("-" * 30)
        result = await session.execute(select(Homework))
        homeworks = result.scalars().all()
        
        if not homeworks:
            print("❌ Домашние задания не найдены")
        else:
            for hw in homeworks:
                status = "✅ Проверено" if hw.is_checked else "⏳ Ожидает проверки"
                print(f"\nЗадание для пользователя {hw.user_id}")
                print(f"   Тема: {hw.topic_id}")
                print(f"   Задание: {hw.task_text[:50]}...")
                print(f"   Ответ: {hw.answer_text[:50] if hw.answer_text else 'Нет ответа'}...")
                print(f"   Статус: {status}")
                print(f"   Выдано: {hw.date_assigned}")
        
        print("\n" + "=" * 60)
        print("✅ Просмотр базы данных завершен!")

if __name__ == "__main__":
    asyncio.run(view_database()) 