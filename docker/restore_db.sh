#!/bin/bash

# Скрипт для восстановления базы данных English Assistant Bot

echo "🔄 Восстановление базы данных..."

# Проверяем аргумент
if [ -z "$1" ]; then
    echo "❌ Укажите файл бэкапа для восстановления"
    echo ""
    echo "📋 Доступные бэкапы:"
    ls -la backups/*.sql 2>/dev/null || echo "   Нет доступных бэкапов"
    echo ""
    echo "💡 Использование:"
    echo "   ./restore_db.sh backups/english_bot_backup_YYYYMMDD_HHMMSS.sql"
    exit 1
fi

BACKUP_FILE="$1"

# Проверяем существование файла
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Файл бэкапа не найден: $BACKUP_FILE"
    exit 1
fi

echo "📁 Восстанавливаем из файла: $BACKUP_FILE"

# Подтверждение
echo "⚠️  ВНИМАНИЕ: Это действие перезапишет текущую базу данных!"
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Восстановление отменено"
    exit 1
fi

# Останавливаем бота
echo "🛑 Останавливаем бота..."
docker-compose stop english-bot

# Восстанавливаем базу данных
echo "🔄 Восстанавливаем базу данных..."
docker-compose exec -T postgres psql -U bot_user english_bot < "$BACKUP_FILE"

# Проверяем успешность восстановления
if [ $? -eq 0 ]; then
    echo "✅ База данных успешно восстановлена"
    
    # Запускаем бота
    echo "🚀 Запускаем бота..."
    docker-compose start english-bot
    
    echo "✅ Восстановление завершено!"
else
    echo "❌ Ошибка при восстановлении базы данных"
    echo "🚀 Запускаем бота..."
    docker-compose start english-bot
    exit 1
fi
