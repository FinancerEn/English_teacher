import asyncio
import os
import logging
from typing import Optional
from aiogram import Dispatcher
from filters.bot import CustomBot
from dotenv import load_dotenv
from aiogram.types import BotCommandScopeAllPrivateChats
from middlewares.db import DataBaseSession
from database.engine import create_db, drop_db, session_maker
from scheduler.lesson_scheduler import LessonScheduler

# Импорты роутеров
from handlers.user_private import router_user_private

load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения 'TOKEN' не задана.")

GROUP_ID_ENV = os.getenv("GROUP_ID")
GROUP_ID: Optional[int] = (
    int(GROUP_ID_ENV) if GROUP_ID_ENV and GROUP_ID_ENV.isdigit() else None
)

db_url = os.getenv("DB_URL")

bot = CustomBot(token=TOKEN)
bot.my_admins_list = []
dp = Dispatcher()

dp.include_router(router_user_private)

# Глобальная переменная для планировщика
lesson_scheduler = None


async def on_startup(bot):
    # Инициализируем OpenAI клиент (автоматически происходит при импорте ai.ai)
    # Раскоментировать если нужно обновить модели,
    # только закоментировать после 1 загрузки сервера.
    # Удаляет содержимое бд
    # await drop_db()

    await create_db()
    
    # Запускаем планировщик
    global lesson_scheduler
    lesson_scheduler = LessonScheduler(bot)
    await lesson_scheduler.start()
    
    print("Бот запущен!")


async def on_shutdown(bot):
    # Останавливаем планировщик
    global lesson_scheduler
    if lesson_scheduler:
        await lesson_scheduler.stop()
    
    print('Бот лёг')


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    # Реализуем наш Middleware слой.
    # Теперь в каждый хендлер нашего проекта будет пробрасываться сессия.
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())