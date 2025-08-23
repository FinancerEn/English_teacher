#!/bin/bash

# Скрипт для очистки English Assistant Bot

echo "🧹 Очистка English Assistant Bot..."

# Подтверждение
echo "⚠️  ВНИМАНИЕ: Это действие удалит все данные и контейнеры!"
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Очистка отменена"
    exit 1
fi

# Останавливаем и удаляем контейнеры
echo "🛑 Останавливаем и удаляем контейнеры..."
docker-compose down -v

# Удаляем образы
echo "🗑️  Удаляем Docker образы..."
docker rmi $(docker images -q english-bot_english-bot) 2>/dev/null || true

# Очищаем неиспользуемые ресурсы Docker
echo "🧹 Очищаем неиспользуемые ресурсы Docker..."
docker system prune -f

# Удаляем директории логов и временных файлов
echo "📁 Удаляем директории логов и временных файлов..."
rm -rf logs temp

echo ""
echo "✅ Очистка завершена!"
echo ""
echo "💡 Для запуска используйте: ./start_project.sh"
