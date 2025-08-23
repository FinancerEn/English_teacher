#!/bin/bash

# Скрипт для остановки English Assistant Bot

echo "🛑 Остановка English Assistant Bot..."

# Останавливаем контейнеры
echo "📦 Останавливаем контейнеры..."
docker-compose down

echo "✅ English Assistant Bot остановлен!"

# Показываем статус
echo "📊 Статус контейнеров:"
docker-compose ps

echo ""
echo "💡 Для запуска используйте: ./start_project.sh"
