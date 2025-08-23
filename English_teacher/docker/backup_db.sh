#!/bin/bash

# Скрипт для резервного копирования базы данных English Assistant Bot

echo "💾 Резервное копирование базы данных..."

# Создаем директорию для бэкапов если её нет
mkdir -p backups

# Генерируем имя файла с текущей датой и временем
BACKUP_FILE="backups/english_bot_backup_$(date +%Y%m%d_%H%M%S).sql"

echo "📁 Создаем бэкап: $BACKUP_FILE"

# Создаем бэкап
docker-compose exec -T postgres pg_dump -U bot_user english_bot > "$BACKUP_FILE"

# Проверяем успешность создания бэкапа
if [ $? -eq 0 ]; then
    echo "✅ Бэкап успешно создан: $BACKUP_FILE"
    
    # Показываем размер файла
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "📊 Размер файла: $FILE_SIZE"
else
    echo "❌ Ошибка при создании бэкапа"
    exit 1
fi

echo ""
echo "💡 Для восстановления из бэкапа используйте:"
echo "   docker-compose exec -T postgres psql -U bot_user english_bot < $BACKUP_FILE"
