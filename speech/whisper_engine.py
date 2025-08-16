import asyncio
import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional

from ai.ai import openai_client

# Настройка логгера
logger = logging.getLogger(__name__)

# Папка для временных аудио файлов
VOICE_CACHE_DIR = Path(__file__).parent / "voice_cache"
VOICE_CACHE_DIR.mkdir(exist_ok=True)

# Режим разработки (без OpenAI API)
DEV_MODE = False  # Измените на True для тестирования без OpenAI API

async def transcribe_audio(audio_path: str) -> str:
    """
    Транскрибирует аудио файл в текст с помощью OpenAI Whisper.
    
    Args:
        audio_path: Путь к аудио файлу
        
    Returns:
        Транскрибированный текст
    """
    
    if DEV_MODE:
        # В режиме разработки возвращаем заглушку
        logger.info("🔧 Режим разработки: заглушка для транскрибации")
        return "Hello, teacher! I am ready for the English lesson."
    
    try:
        # Используем OpenAI Whisper для транскрибации
        transcribed_text = await openai_client.transcribe_audio(audio_path)
        
        if not transcribed_text.strip():
            transcribed_text = "Hello, teacher! I am ready for the English lesson."
        
        logger.info(f"✅ Транскрибированный текст: '{transcribed_text}'")
        return transcribed_text
        
    except Exception as e:
        logger.error(f"❌ Ошибка при транскрибации: {e}")
        return "Hello, teacher! I am ready for the English lesson."

async def generate_speech(text: str) -> bytes:
    """
    Генерирует речь из текста с помощью OpenAI TTS.
    
    Args:
        text: Текст для озвучивания
        
    Returns:
        Байты аудио файла
    """
    
    if DEV_MODE:
        # В режиме разработки возвращаем пустые байты
        logger.info("🔧 Режим разработки: заглушка для TTS")
        return b""
    
    try:
        # Используем OpenAI TTS для генерации речи
        audio_bytes = await openai_client.generate_speech(text)
        
        logger.info(f"✅ Сгенерирована речь для текста: '{text[:50]}...'")
        return audio_bytes
        
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации речи: {e}")
        return b""

async def save_audio_to_file(audio_bytes: bytes, filename: str) -> str:
    """
    Сохраняет аудио байты в файл.
    
    Args:
        audio_bytes: Байты аудио файла
        filename: Имя файла
        
    Returns:
        Путь к сохранённому файлу
    """
    
    if not audio_bytes:
        logger.warning("⚠️ Пустые аудио байты, пропускаем сохранение")
        return ""
    
    try:
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_path = temp_file.name
        
        # Сохраняем аудио байты в файл
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        logger.info(f"✅ Аудио файл сохранён: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении аудио файла: {e}")
        return ""

def get_voice_cache_dir() -> Path:
    """
    Возвращает путь к папке кэша голосовых файлов.
    
    Returns:
        Путь к папке кэша
    """
    return VOICE_CACHE_DIR

def cleanup_temp_files():
    """
    Очищает временные файлы в кэше.
    """
    try:
        for file_path in VOICE_CACHE_DIR.glob("*.mp3"):
            try:
                file_path.unlink()
                logger.info(f"🗑️ Удалён временный файл: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить файл {file_path}: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке временных файлов: {e}")

# Функции для совместимости со старым кодом
def load_model() -> None:
    """
    Заглушка для совместимости со старым кодом.
    """
    logger.info("🔧 load_model() - заглушка для совместимости")

def get_model():
    """
    Заглушка для совместимости со старым кодом.
    """
    logger.info("🔧 get_model() - заглушка для совместимости")
    return None

def get_ffmpeg_path() -> str:
    """
    Заглушка для совместимости со старым кодом.
    """
    logger.info("🔧 get_ffmpeg_path() - заглушка для совместимости")
    return "ffmpeg"

def convert_audio(input_path: str, output_path: str) -> str:
    """
    Заглушка для совместимости со старым кодом.
    """
    logger.info("🔧 convert_audio() - заглушка для совместимости")
    return output_path

def recognize_audio(path_to_ogg: str) -> str:
    """
    Заглушка для совместимости со старым кодом.
    """
    logger.info("🔧 recognize_audio() - заглушка для совместимости")
    return "Hello, teacher! I am ready for the English lesson." 