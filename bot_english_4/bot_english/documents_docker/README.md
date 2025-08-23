# 🐳 English Assistant Bot - Docker развертывание

## 📋 Быстрый старт

### 1. Подготовка
```bash
# Переходим в папку docker
cd docker

# Копируем пример .env файла
cp env.example .env

# Редактируем .env файл с вашими ключами
nano .env
```

### 2. Запуск
```bash
# Запускаем проект
./start_project.sh
```

### 3. Проверка
```bash
# Смотрим статус
docker-compose ps

# Смотрим логи
./logs.sh all
```

## 📁 Структура Docker файлов

```
docker/
├── Dockerfile                    # Образ приложения
├── docker-compose.yml           # Оркестрация контейнеров
├── env.example                  # Пример переменных окружения
├── start_project.sh             # Запуск проекта
├── stop_project.sh              # Остановка проекта
├── restart_project.sh           # Перезапуск проекта
├── logs.sh                      # Просмотр логов
├── backup_db.sh                 # Резервное копирование БД
├── restore_db.sh                # Восстановление БД
└── clean_project.sh             # Очистка проекта
```

## 🔧 Управление проектом

### Основные команды:

#### Запуск:
```bash
./start_project.sh
```

#### Остановка:
```bash
./stop_project.sh
```

#### Перезапуск:
```bash
./restart_project.sh
```

#### Просмотр логов:
```bash
./logs.sh bot      # Логи бота
./logs.sh db       # Логи базы данных
./logs.sh all      # Все логи
```

#### Резервное копирование:
```bash
./backup_db.sh
```

#### Восстановление:
```bash
./restore_db.sh backups/english_bot_backup_YYYYMMDD_HHMMSS.sql
```

#### Очистка:
```bash
./clean_project.sh
```

## 🌐 Доступ к сервисам

### База данных PostgreSQL:
- **Хост:** localhost
- **Порт:** 5434
- **База данных:** english_bot
- **Пользователь:** bot_user
- **Пароль:** указан в .env файле

### Подключение к БД:
```bash
# Через Docker
docker-compose exec postgres psql -U bot_user -d english_bot

# Через внешний клиент
psql -h localhost -p 5434 -U bot_user -d english_bot
```

## 📝 Настройка переменных окружения

### Обязательные переменные (.env):

```env
# Telegram Bot
TOKEN=your_telegram_bot_token_here
GROUP_ID=your_telegram_group_id_here

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# База данных
DB_PASSWORD=your_secure_password_here
DB_URL=postgresql://bot_user:your_secure_password_here@postgres:5432/english_bot

# Время уроков
TIMEZONE=Asia/Shanghai
LESSON_TIME=12:00

# Режим работы
TEST_MODE=false
TEST_INTERVAL_MINUTES=10
```

### Получение ключей:

#### Telegram Bot Token:
1. Напишите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте полученный токен

#### OpenAI API Key:
1. Зайдите на https://platform.openai.com
2. Создайте аккаунт или войдите
3. Перейдите в API Keys
4. Создайте новый ключ

#### Telegram Group ID:
1. Добавьте бота в группу
2. Отправьте сообщение в группу
3. Перейдите на https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
4. Найдите `"chat":{"id":-1001234567890}`

## 🔍 Мониторинг и диагностика

### Проверка статуса:
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Логи в реальном времени
./logs.sh all
```

### Диагностика проблем:

#### Бот не запускается:
```bash
# Проверяем логи бота
./logs.sh bot

# Проверяем переменные окружения
docker-compose exec english-bot env | grep -E "(TOKEN|OPENAI|DB_URL)"
```

#### Проблемы с базой данных:
```bash
# Проверяем логи БД
./logs.sh db

# Проверяем подключение
docker-compose exec postgres psql -U bot_user -d english_bot -c "\dt"
```

#### Проблемы с памятью:
```bash
# Очистка неиспользуемых ресурсов
docker system prune -a
```

## 🛠 Устранение неполадок

### Частые проблемы:

#### 1. Ошибка "Permission denied":
```bash
# Делаем скрипты исполняемыми
chmod +x *.sh
```

#### 2. Ошибка "Port already in use":
```bash
# Проверяем занятые порты
netstat -tlnp | grep 5434

# Останавливаем конфликтующие сервисы
docker-compose down
```

#### 3. Ошибка "Database connection failed":
```bash
# Перезапускаем базу данных
docker-compose restart postgres

# Ждем запуска и проверяем
sleep 10
./logs.sh db
```

#### 4. Ошибка "OpenAI API key invalid":
```bash
# Проверяем ключ в .env файле
cat .env | grep OPENAI_API_KEY

# Обновляем ключ и перезапускаем
docker-compose restart english-bot
```

## 📊 Резервное копирование

### Автоматическое резервное копирование:
```bash
# Создание бэкапа
./backup_db.sh

# Восстановление из бэкапа
./restore_db.sh backups/english_bot_backup_20240814_201500.sql
```

### Планирование автоматических бэкапов:
```bash
# Добавляем в crontab (ежедневно в 2:00)
0 2 * * * cd /path/to/project/docker && ./backup_db.sh
```

## 🔄 Обновление проекта

### Обновление кода:
```bash
# Останавливаем проект
./stop_project.sh

# Обновляем код (git pull или копирование файлов)

# Пересобираем образы
docker-compose build --no-cache

# Запускаем проект
./start_project.sh
```

### Обновление переменных окружения:
```bash
# Редактируем .env файл
nano .env

# Перезапускаем проект
./restart_project.sh
```

## 📞 Поддержка

### Полезные команды:
```bash
# Информация о системе
docker version
docker-compose version
docker system info

# Статус всех сервисов
docker-compose ps
docker stats

# Проверка портов
netstat -tlnp | grep -E "(5434|80|443)"
```

### Логи для диагностики:
- **Логи приложения:** `./logs.sh bot`
- **Логи базы данных:** `./logs.sh db`
- **Системные логи:** `docker system events`

### Контакты:
- Документация проекта: `../documentations/PROJECT_GUIDE.md`
- Руководство по деплою: `../documentations/DEPLOYMENT_DOCKER.md`
