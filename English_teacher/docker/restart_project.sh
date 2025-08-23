#!/bin/bash

# Скрипт для перезапуска English Assistant Bot

echo "🔄 Перезапуск English Assistant Bot..."

# Останавливаем контейнеры
echo "🛑 Останавливаем контейнеры..."
docker-compose down

# Запускаем контейнеры
echo "🚀 Запускаем контейнеры..."
docker-compose up -d

# Ждём немного и проверяем статус
echo "⏳ Ждем запуска сервисов..."
sleep 5

echo "📊 Статус контейнеров:"
docker-compose ps

echo ""
echo "✅ English Assistant Bot перезапущен!"
echo ""
echo "🔍 Для просмотра логов:"
echo "   docker-compose logs -f"
