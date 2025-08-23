# Файл, ассинхронный движок ORM. Реализуем возможность работать с базой данных через models.
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base

from dotenv import load_dotenv
load_dotenv()

# Получаем URL БД sqlite из .env
# db_url = os.getenv("DB_URL_SQLITE")

# Получаем URL БД postgres из .env
db_url = os.getenv("DB_URL")

# print(f"DB_URL загружен: {db_url}")

# Проверяем, что URL не пустой
# print(f"DB_URL загружен: {db_url}")
if not db_url:
    raise ValueError("Переменная окружения DB_URL не задана!")

engine = create_async_engine(db_url, echo=True)
session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
