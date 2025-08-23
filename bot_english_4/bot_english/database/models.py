from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from sqlalchemy import func

Base = declarative_base()


class Topic(Base):
    """
    Модель для хранения тем школьной программы.
    """
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)  # Название темы
    description = Column(Text, nullable=False)   # Описание темы
    tasks = Column(Text, nullable=False)         # Задания (JSON-строка)
    is_completed = Column(Boolean, default=False)  # Пройдена ли тема


class User(Base):
    """
    Модель для хранения информации о пользователе и его прогрессе.
    """
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)  # Telegram user id
    current_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)  # Текущая тема
    last_lesson_date = Column(DateTime, nullable=True)  # Дата последнего урока
    progress = Column(Text, default="[]")  # JSON: список id пройденных тем
    created_at = Column(DateTime, default=datetime.utcnow)  # Дата регистрации

    # Связи с другими таблицами
    topic = relationship("Topic", foreign_keys=[current_topic_id])
    messages = relationship("MessageHistory", back_populates="user")
    homeworks = relationship("Homework", back_populates="user")


class MessageHistory(Base):
    """
    Модель для хранения истории сообщений (20 последних для каждого пользователя).
    """
    __tablename__ = "message_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)  # ID пользователя
    role = Column(String(10), nullable=False)  # "bot" или "user"
    content = Column(Text, nullable=False)  # Текст сообщения
    voice_file_id = Column(String(255), nullable=True)  # ID голосового файла в Telegram
    timestamp = Column(DateTime, default=datetime.utcnow)  # Время отправки

    # Связь с пользователем
    user = relationship("User", back_populates="messages")


class Homework(Base):
    """
    Модель для хранения домашних заданий.
    """
    __tablename__ = "homeworks"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)  # ID пользователя
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)  # ID темы
    task_text = Column(Text, nullable=False)  # Текст задания
    answer_text = Column(Text, nullable=True)  # Ответ пользователя
    is_checked = Column(Boolean, default=False)  # Проверено ли
    is_passed = Column(Boolean, default=False)  # Зачтено ли
    date_assigned = Column(DateTime, default=datetime.utcnow)  # Дата выдачи
    date_checked = Column(DateTime, nullable=True)  # Дата проверки

    # Связи с другими таблицами
    user = relationship("User", back_populates="homeworks")
    topic = relationship("Topic")