#!/bin/bash

# Скрипт для запуска English Assistant Bot в Docker

set -e  # Остановиться при ошибке

echo "🎓 Запуск English Assistant Bot..."

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и попробуйте снова."
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose и попробуйте снова."
    exit 1
fi

# Проверяем наличие .env файла в корне проекта
if [ ! -f ../.env ]; then
    echo "❌ Файл .env не найден в корне проекта!"
    echo "📝 Создайте файл .env в корне проекта с необходимыми переменными:"
    echo "   TOKEN=your_telegram_bot_token_here"
    echo "   GROUP_ID=your_telegram_group_id_here"
    echo "   OPENAI_API_KEY=your_openai_api_key_here"
    echo "   DB_PASSWORD=your_secure_password_here"
    echo "   DB_URL=postgresql://bot_user:your_secure_password_here@postgres:5432/english_bot"
    echo "   TIMEZONE=Asia/Shanghai"
    echo "   LESSON_TIME=12:00"
    echo "   TEST_MODE=false"
    echo "   TEST_INTERVAL_MINUTES=10"
    echo ""
    echo "💡 Скопируйте env.example в .env и отредактируйте:"
    echo "   cp env.example ../.env"
    exit 1
fi

# Проверяем, что TOKEN не пустой
if ! grep -q "TOKEN=" ../.env || grep -q "TOKEN=$" ../.env; then
    echo "❌ TOKEN не настроен в файле .env"
    echo "📝 Укажите ваш Telegram Bot Token в файле .env"
    exit 1
fi

# Проверяем, что OPENAI_API_KEY не пустой
if ! grep -q "OPENAI_API_KEY=" ../.env || grep -q "OPENAI_API_KEY=$" ../.env; then
    echo "❌ OPENAI_API_KEY не настроен в файле .env"
    echo "📝 Укажите ваш OpenAI API Key в файле .env"
    exit 1
fi

# Проверяем, что DB_PASSWORD не пустой
if ! grep -q "DB_PASSWORD=" ../.env || grep -q "DB_PASSWORD=$" ../.env; then
    echo "❌ DB_PASSWORD не настроен в файле .env"
    echo "📝 Укажите пароль для базы данных в файле .env"
    exit 1
fi

echo "✅ Все проверки пройдены!"

# Создаем директории для логов и временных файлов
echo "📁 Создаем директории..."
mkdir -p logs temp

# Останавливаем существующие контейнеры (если есть)
echo "🛑 Останавливаем существующие контейнеры..."
docker-compose down 2>/dev/null || true

# Собираем образы
echo "🔨 Собираем Docker образы..."
docker-compose build --no-cache

# Запускаем сервисы
echo "🚀 Запускаем сервисы..."
docker-compose up -d

# Ждём немного и проверяем статус
echo "⏳ Ждем запуска сервисов..."
sleep 10

echo "📊 Статус контейнеров:"
docker-compose ps

# Проверяем логи базы данных
echo "🔍 Проверяем логи базы данных..."
if docker-compose logs postgres | grep -q "database system is ready to accept connections"; then
    echo "✅ База данных успешно запущена"
else
    echo "⚠️  База данных может еще запускаться..."
fi

# Проверяем логи бота
echo "🔍 Проверяем логи бота..."
if docker-compose logs english-bot | grep -q "Bot started"; then
    echo "✅ Бот успешно запущен"
else
    echo "⚠️  Бот может еще запускаться..."
fi

echo ""
echo "✅ English Assistant Bot запущен!"
echo ""
echo "🔧 Полезные команды:"
echo "   Логи приложения:    docker-compose logs -f english-bot"
echo "   Логи базы данных:   docker-compose logs -f postgres"
echo "   Остановить:         docker-compose down"
echo "   Перезапустить:      docker-compose restart english-bot"
echo "   Статус:             docker-compose ps"
echo ""
echo "🔍 Для просмотра логов в реальном времени:"
echo "   docker-compose logs -f"
echo ""
echo "🌐 База данных доступна на порту 5434"
echo "   Подключение: localhost:5434"
echo "   Пользователь: bot_user"
echo "   База данных: english_bot"
echo "   Пароль: указан в .env файле"
echo ""
echo "📱 Теперь можете протестировать бота в Telegram!"
