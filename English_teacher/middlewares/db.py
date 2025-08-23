"""
Этот файл создаёт Middleware слой, который автоматически передаёт сессию базы данных в каждый хендлер.
Что делает Middleware: 1)Перехватывает событие до обработки хендлером.
2) Создаёт новую асинхронную сессию базы данных. 3) Добавляет её в data['session'],
чтобы она была доступна в хендлерах. 4) Вызывает хендлер, передавая ему event и data.

Теперь любой хендлер, принимающий data, может работать с data['session'], то есть с базой данных.
"""
from typing import Dict, Awaitable, Callable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)


class DataBaseSession(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data['session'] = session
            try:
                return await handler(event, data)
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                await session.rollback()
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()