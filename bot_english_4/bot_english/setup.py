#!/usr/bin/env python3
"""
Скрипт для автоматической инициализации проекта English Tutor Bot
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command: str, description: str) -> bool:
    """
    Выполняет команду и выводит результат
    
    Args:
        command: Команда для выполнения
        description: Описание команды
        
    Returns:
        True если команда выполнена успешно, False иначе
    """
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} выполнено успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при {description.lower()}: {e}")
        print(f"Вывод ошибки: {e.stderr}")
        return False


def create_env_file():
    """
    Создаёт файл .env из env.example если он не существует
    """
    if not os.path.exists('.env'):
        print("📝 Создание файла .env...")
        try:
            with open('env.example', 'r', encoding='utf-8') as example:
                content = example.read()
            
            with open('.env', 'w', encoding='utf-8') as env:
                env.write(content)
            
            print("✅ Файл .env создан из env.example")
            print("⚠️  Не забудьте заполнить переменные окружения в .env файле!")
        except Exception as e:
            print(f"❌ Ошибка при создании .env файла: {e}")
    else:
        print("✅ Файл .env уже существует")


def check_python_version():
    """
    Проверяет версию Python
    
    Returns:
        True если версия подходящая, False иначе
    """
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"Текущая версия: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Версия Python: {version.major}.{version.minor}.{version.micro}")
    return True


def create_directories():
    """
    Создаёт необходимые директории
    """
    directories = ['logs', 'temp', 'audio']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Создана директория: {directory}")


def main():
    """
    Основная функция инициализации
    """
    print("🚀 Инициализация проекта English Tutor Bot")
    print("=" * 50)
    
    # Проверяем версию Python
    if not check_python_version():
        sys.exit(1)
    
    # Создаём необходимые директории
    create_directories()
    
    # Создаём .env файл
    create_env_file()
    
    # Устанавливаем зависимости
    if not run_command("pip install -r requirements.txt", "Установка зависимостей"):
        print("❌ Не удалось установить зависимости")
        sys.exit(1)
    
    # Инициализируем базу данных
    if os.path.exists('database/load_topics.py'):
        if not run_command("python database/load_topics.py", "Инициализация базы данных"):
            print("⚠️  Не удалось инициализировать базу данных")
    
    print("\n" + "=" * 50)
    print("🎉 Инициализация завершена!")
    print("\n📋 Следующие шаги:")
    print("1. Отредактируйте файл .env и заполните переменные окружения")
    print("2. Получите TOKEN бота у @BotFather")
    print("3. Получите OPENAI_API_KEY на https://platform.openai.com/")
    print("4. Запустите бота командой: python app.py")
    print("\n📚 Дополнительная информация в README.md")


if __name__ == "__main__":
    main() 