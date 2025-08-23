#!/bin/bash

# Скрипт для полной автоматической установки English Assistant Bot на сервер

set -e  # Остановиться при ошибке

echo "🎓 Установка English Assistant Bot на сервер..."
echo "================================================"

# Проверяем, что мы root или используем sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Этот скрипт должен выполняться с правами root (sudo)"
    echo "💡 Запустите: sudo ./install_server.sh"
    exit 1
fi

# Обновляем систему
echo "📦 Обновляем систему..."
apt update && apt upgrade -y

# Устанавливаем необходимые пакеты
echo "📦 Устанавливаем необходимые пакеты..."
apt install -y curl wget git nano htop

# Устанавливаем Docker
echo "🐳 Устанавливаем Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker установлен"
else
    echo "✅ Docker уже установлен"
fi

# Устанавливаем Docker Compose
echo "🐳 Устанавливаем Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose установлен"
else
    echo "✅ Docker Compose уже установлен"
fi

# Добавляем пользователя в группу docker
echo "👤 Настраиваем права пользователя..."
if id -nG "$SUDO_USER" | grep -qw docker; then
    echo "✅ Пользователь уже в группе docker"
else
    usermod -aG docker $SUDO_USER
    echo "✅ Пользователь добавлен в группу docker"
fi

# Создаем директорию для проекта
echo "📁 Создаем директорию проекта..."
mkdir -p /home/$SUDO_USER/bots
cd /home/$SUDO_USER/bots

# Клонируем проект (если репозиторий доступен)
echo "📥 Клонируем проект..."
if [ -d "english" ]; then
    echo "✅ Проект уже существует"
    cd english
else
    echo "❌ Проект не найден. Пожалуйста, скопируйте файлы проекта в /home/$SUDO_USER/bots/english/"
    echo "💡 Или клонируйте репозиторий: git clone <your-repo-url> english"
    exit 1
fi

# Передаем права на файлы пользователю
echo "🔐 Настраиваем права доступа..."
chown -R $SUDO_USER:$SUDO_USER /home/$SUDO_USER/bots/english

# Переключаемся на пользователя
echo "👤 Переключаемся на пользователя $SUDO_USER..."
su - $SUDO_USER << 'EOF'
cd ~/bots/english

# Делаем скрипты исполняемыми
chmod +x *.sh

# Создаем .env файл если его нет
if [ ! -f ".env" ]; then
    echo "📝 Создаем .env файл..."
    cat > .env << 'ENVEOF'
# Telegram Bot Configuration
TOKEN=your_telegram_bot_token_here
GROUP_ID=your_telegram_group_id_here

# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
DB_PASSWORD=44_assistent_l44
DB_URL=postgresql+asyncpg://assistent:44_assistent_l44@postgres:5432/english

# Timezone and Schedule Configuration
TIMEZONE=Asia/Shanghai
LESSON_TIME=12:00

# Test Mode Configuration
TEST_MODE=true
TEST_INTERVAL_MINUTES=6
ENVEOF
    echo "✅ .env файл создан"
    echo "⚠️  Не забудьте отредактировать .env файл с вашими ключами!"
fi

echo "🚀 Запускаем проект..."
./start_project.sh
EOF

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Отредактируйте .env файл: nano /home/$SUDO_USER/bots/english/.env"
echo "2. Укажите ваши Telegram Bot Token и OpenAI API Key"
echo "3. Перезапустите проект: cd ~/bots/english && ./start_project.sh"
echo ""
echo "🔧 Полезные команды:"
echo "   Логи: cd ~/bots/english && docker-compose logs -f"
echo "   Статус: cd ~/bots/english && docker-compose ps"
echo "   Остановить: cd ~/bots/english && docker-compose down"
echo ""
echo "📱 После настройки .env файла бот будет готов к работе!"

