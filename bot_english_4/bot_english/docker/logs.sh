#!/bin/bash

# Скрипт для просмотра логов English Assistant Bot

echo "📋 Логи English Assistant Bot"
echo ""

# Проверяем аргументы
if [ "$1" = "bot" ]; then
    echo "🤖 Логи бота:"
    docker-compose logs -f english-bot
elif [ "$1" = "db" ]; then
    echo "🗄️  Логи базы данных:"
    docker-compose logs -f postgres
elif [ "$1" = "all" ]; then
    echo "📊 Все логи:"
    docker-compose logs -f
else
    echo "❓ Использование:"
    echo "   ./logs.sh bot    - логи бота"
    echo "   ./logs.sh db     - логи базы данных"
    echo "   ./logs.sh all    - все логи"
    echo ""
    echo "💡 Для выхода из просмотра логов нажмите Ctrl+C"
fi
