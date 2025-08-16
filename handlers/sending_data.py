from aiogram.types import Message
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime
from aiogram import Bot, types
from database.models import MessageHistory, Homework
from aiogram import exceptions as tg_exceptions
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

load_dotenv()

GROUP_ID_ENV = os.getenv("GROUP_ID")
if not GROUP_ID_ENV:
    print("⚠️ GROUP_ID не задан в .env! Отправка в группу отключена.")
    GROUP_ID = None
else:
    try:
        GROUP_ID: int = int(GROUP_ID_ENV)
    except ValueError:
        print(f"⚠️ GROUP_ID в .env должен быть целым числом, а не {GROUP_ID_ENV!r}")
        GROUP_ID = None


async def save_lesson_dialog(session: AsyncSession, user_id: int, user_message: str, ai_response: str, voice_file_id: str = None):
    """
    Сохраняет диалог урока в базу данных.
    """
    try:
        new_message = MessageHistory(
            user_id=user_id,
            role="user",
            content=user_message,
            voice_file_id=voice_file_id,
            timestamp=datetime.utcnow()
        )
        session.add(new_message)
        
        # Сохраняем ответ ассистента отдельно
        ai_message = MessageHistory(
            user_id=user_id,
            role="bot",
            content=ai_response,
            voice_file_id=None,
            timestamp=datetime.utcnow()
        )
        session.add(ai_message)
        await session.commit()
        print(f"✅ Диалог урока сохранен для пользователя {user_id}")
        return True
    except Exception as e:
        await session.rollback()
        print(f"❌ Ошибка при сохранении диалога: {e}")
        return False


async def save_homework(session: AsyncSession, user_id: int, topic_id: int, homework_text: str):
    """
    Сохраняет домашнее задание в базу данных.
    """
    try:
        new_homework = Homework(
            user_id=user_id,
            topic_id=topic_id,
            task_text=homework_text,
            answer_text=None,  # Пока нет ответа
            is_checked=False,
            is_passed=False,
            date_assigned=datetime.utcnow()
        )
        session.add(new_homework)
        await session.commit()
        print(f"✅ Домашнее задание сохранено для пользователя {user_id}")
        return True
    except Exception as e:
        await session.rollback()
        print(f"❌ Ошибка при сохранении домашнего задания: {e}")
        return False


async def send_lesson_summary_to_group(bot: Bot, user_id: int, user_name: str, lesson_dialogs: list, homework_text: str = None):
    """
    Отправляет в Telegram-группу сводку урока с диалогами и домашним заданием.
    """
    if not GROUP_ID:
        print("⚠️ GROUP_ID не настроен, отправка в группу пропущена")
        return
    
    try:
        # Формируем заголовок урока
        header_message = (
            f"📚 ЗАВЕРШЕН УРОК АНГЛИЙСКОГО ЯЗЫКА\n"
            f"👤 Ученик: {user_name}\n"
            f"🆔 ID: {user_id}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"💬 Количество диалогов: {len(lesson_dialogs)}\n"
            f"{'='*40}"
        )
        
        # Отправляем заголовок
        await bot.send_message(
            chat_id=GROUP_ID,
            text=header_message,
            parse_mode=None
        )
        
        # Отправляем диалоги
        for i, dialog in enumerate(lesson_dialogs, 1):
            dialog_text = (
                f"💬 Диалог #{i}\n"
                f"👤 Ученик: {dialog['user_message'][:100]}{'...' if len(dialog['user_message']) > 100 else ''}\n"
                f"🤖 Ассистент: {dialog['ai_response'][:100]}{'...' if len(dialog['ai_response']) > 100 else ''}\n"
                f"⏰ Время: {dialog['timestamp'].strftime('%H:%M:%S')}\n"
                f"{'-'*30}"
            )
            
            await bot.send_message(
                chat_id=GROUP_ID,
                text=dialog_text,
                parse_mode=None
            )
            
            # Небольшая задержка между сообщениями
            await asyncio.sleep(0.5)
        
        # Отправляем домашнее задание, если есть
        if homework_text:
            homework_message = (
                f"📝 ДОМАШНЕЕ ЗАДАНИЕ\n"
                f"👤 Ученик: {user_name}\n"
                f"🆔 ID: {user_id}\n"
                f"📋 Задание:\n{homework_text}\n"
                f"{'='*40}"
            )
            
            await bot.send_message(
                chat_id=GROUP_ID,
                text=homework_message,
                parse_mode=None
            )
        
        print(f"✅ Сводка урока отправлена в группу для пользователя {user_id}")
        
    except tg_exceptions.TelegramBadRequest as e:
        print(f"❌ Ошибка Telegram при отправке сводки в группу: {e}")
        if "chat not found" in str(e).lower():
            print(f"Группа с ID {GROUP_ID} не найдена")
        elif "bot was blocked" in str(e).lower():
            print("Бот заблокирован в группе")
        elif "chat is deactivated" in str(e).lower():
            print("Группа деактивирована")
        else:
            print(f"Другая ошибка Telegram: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка при отправке сводки в группу: {e}")


async def send_homework_response_to_group(bot: Bot, user_id: int, user_name: str, homework_text: str, user_answer: str):
    """
    Отправляет в Telegram-группу ответ ученика на домашнее задание.
    """
    if not GROUP_ID:
        print("⚠️ GROUP_ID не настроен, отправка в группу пропущена")
        return
    
    try:
        homework_response_message = (
            f"📝 ОТВЕТ НА ДОМАШНЕЕ ЗАДАНИЕ\n"
            f"👤 Ученик: {user_name}\n"
            f"🆔 ID: {user_id}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📋 Задание:\n{homework_text[:200]}{'...' if len(homework_text) > 200 else ''}\n"
            f"✏️ Ответ ученика:\n{user_answer[:300]}{'...' if len(user_answer) > 300 else ''}\n"
            f"{'='*40}"
        )
        
        await bot.send_message(
            chat_id=GROUP_ID,
            text=homework_response_message,
            parse_mode=None
        )
        
        print(f"✅ Ответ на ДЗ отправлен в группу для пользователя {user_id}")
        
    except tg_exceptions.TelegramBadRequest as e:
        print(f"❌ Ошибка Telegram при отправке ответа на ДЗ: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка при отправке ответа на ДЗ: {e}")


async def get_lesson_dialogs(session: AsyncSession, user_id: int, limit: int = 10) -> list:
    """
    Получает последние диалоги урока для пользователя.
    """
    try:
        result = await session.execute(
            select(MessageHistory)
            .where(MessageHistory.user_id == user_id)
            .order_by(MessageHistory.timestamp.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        dialogs = []
        # Группируем сообщения пользователя и бота в пары
        user_messages = [msg for msg in messages if msg.role == "user"]
        bot_messages = [msg for msg in messages if msg.role == "bot"]
        
        # Создаем пары диалогов
        for i in range(min(len(user_messages), len(bot_messages))):
            dialogs.append({
                'user_message': user_messages[i].content,
                'ai_response': bot_messages[i].content,
                'timestamp': user_messages[i].timestamp
            })
        
        return dialogs
    except Exception as e:
        print(f"❌ Ошибка при получении диалогов: {e}")
        return []


async def update_homework_answer(session: AsyncSession, user_id: int, answer_text: str):
    """
    Обновляет ответ пользователя на домашнее задание.
    """
    try:
        # Находим последнее незавершенное домашнее задание
        result = await session.execute(
            select(Homework)
            .where(
                Homework.user_id == user_id,
                Homework.is_checked == False
            )
            .order_by(Homework.date_assigned.desc())
            .limit(1)
        )
        homework = result.scalar_one_or_none()
        
        if homework:
            homework.answer_text = answer_text
            homework.is_checked = True
            homework.date_checked = datetime.utcnow()
            homework.is_passed = True  # TODO: Здесь будет проверка через ИИ
            
            await session.commit()
            print(f"✅ Ответ на ДЗ обновлен для пользователя {user_id}")
            return homework
        else:
            print(f"⚠️ Не найдено незавершенное ДЗ для пользователя {user_id}")
            return None
            
    except Exception as e:
        await session.rollback()
        print(f"❌ Ошибка при обновлении ответа на ДЗ: {e}")
        return None 