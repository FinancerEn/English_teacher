# 🎓 English Assistant Bot

Telegram бот для обучения английскому языку с использованием OpenAI API (GPT-4o-mini, Whisper, TTS).

## 🚀 Полная установка на сервер (автоматическая)

### Вариант 1: Автоматическая установка (рекомендуется)

1. **Скопируйте файлы проекта на сервер** в папку `/home/username/bots/english/`

2. **Запустите автоматическую установку:**
```bash
cd /home/username/bots/english
chmod +x install_server.sh
sudo ./install_server.sh
```

3. **Настройте переменные окружения:**
```bash
nano .env
```
Замените значения на ваши:
- `TOKEN=your_telegram_bot_token`
- `GROUP_ID=your_telegram_group_id`
- `OPENAI_API_KEY=your_openai_api_key`

4. **Перезапустите проект:**
```bash
./start_project.sh
```

### Вариант 2: Ручная установка

#### 1. Подготовка сервера
```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Устанавливаем Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Добавляем пользователя в группу docker
sudo usermod -aG docker $USER
# Перезайти в систему или выполнить: newgrp docker
```

#### 2. Клонирование и настройка
```bash
# Клонируем проект
cd ~
git clone <your-repo-url> bots/english
cd bots/english

# Создаем .env файл
cp env.example .env
nano .env  # Редактируем переменные окружения
```

#### 3. Первый запуск
```bash
# Делаем скрипты исполняемыми
chmod +x *.sh

# Запускаем проект (автоматически загружает базу знаний)
./start_project.sh
```

## 🔄 Управление проектом

### Перезапуск
```bash
cd ~/bots/english
docker-compose down
docker-compose up -d
```

### Быстрый перезапуск
```bash
cd ~/bots/english
docker-compose restart
```

### Пересборка образа
```bash
cd ~/bots/english
# Останавливает все контейнеры, определенные в docker-compose.yml. Удаляет контейнеры из  памяти
docker-compose down
# Пересобирает Docker образ для сервиса english-bot. Флаг --no-cache - игнорирует кэш и собирает образ с нуля
docker-compose build --no-cache
# Создает новые контейнеры с чистым образом. Запускает PostgreSQL с пустой базой данных. Запускает бота с обновленным кодом
docker-compose up -d
```

## 📊 Мониторинг

### Просмотр логов
```bash
# Все сервисы
docker-compose logs -f

# Только бот
docker-compose logs -f english-bot

# Только база данных
docker-compose logs -f postgres
```

### Статус контейнеров
```bash
docker-compose ps
```

## 🗄️ База данных

### Настройка базы данных

**ВАЖНО**: Перед первым запуском необходимо создать файл `database/init.sql`:

```bash
cd ~/bots/english
cp database/init.sql.example database/init.sql
nano database/init.sql
```

В файле `init.sql.example` замените placeholder'ы на ваши данные и замени название на init.sql:
- `[YOUR_DB_NAME]` → имя вашей базы данных (например: `english`)
- `[YOUR_DB_USER]` → имя пользователя БД (например: `assistent`)

**Пример настроенного файла:**
```sql
-- Даём пользователю assistent полные права на базу данных english
GRANT ALL PRIVILEGES ON DATABASE english TO assistent;
-- Подключаемся к базе данных english
\c english;
-- ... остальные настройки
```

### Автоматическая загрузка
База знаний загружается автоматически при запуске `./start_project.sh`

### Ручная загрузка базы знаний
```bash
cd ~/bots/english
docker-compose exec english-bot python database/load_topics.py
```

### Проверка базы данных
```bash
# Подключение к PostgreSQL
docker-compose exec postgres psql -U assistent -d english

# Проверка количества тем
docker-compose exec postgres psql -U assistent -d english -c "SELECT COUNT(*) FROM topics;"
```

### Полная пересоздание базы
```bash
cd ~/bots/english
docker-compose down
docker volume rm bot_english_postgres_data
docker-compose up -d
```

## 🛠️ Внесение изменений

### Редактирование файлов
```bash
# Редактируем файлы на сервере
nano app.py
nano handlers/user_private.py
# и т.д.
```

### Применение изменений
```bash
# После изменения кода
cd ~/bots/english
docker-compose restart english-bot

# После изменения зависимостей
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 🛠️ Полезные команды

### Очистка
```bash
# Остановить все контейнеры
docker-compose down

# Удалить все образы и тома
docker-compose down -v
docker system prune -a

# Очистить логи
docker system prune -f
```

### Резервное копирование
```bash
# Экспорт базы данных
docker-compose exec postgres pg_dump -U assistent english > backup.sql

# Восстановление
docker-compose exec -T postgres psql -U assistent english < backup.sql
```

## ⚡ Быстрые команды для копирования

```bash
# Полная установка
sudo ./install_server.sh

# Настройка базы данных (ПЕРЕД первым запуском)
cd ~/bots/english
cp database/init.sql.example database/init.sql
nano database/init.sql  # Замените [YOUR_DB_NAME] и [YOUR_DB_USER]

# Запуск
cd ~/bots/english && ./start_project.sh

# Перезапуск
cd ~/bots/english && docker-compose restart

# Логи
docker-compose logs -f

# Загрузка базы знаний
docker-compose exec english-bot python database/load_topics.py
```

## 📁 Структура проекта
```
~/bots/english/
├── app.py                 # Главный файл приложения
├── docker-compose.yml     # Конфигурация Docker
├── Dockerfile            # Образ приложения
├── .env                  # Переменные окружения
├── requirements.txt      # Python зависимости
├── install_server.sh     # Автоматическая установка
├── start_project.sh      # Запуск проекта
├── database/            # База данных
│   ├── load_topics.py   # Скрипт загрузки тем
│   ├── init.sql.example # Шаблон инициализации БД
│   └── init.sql        # Инициализация БД (создать из .example)
├── handlers/           # Обработчики Telegram
├── ai/                # AI интеграция
└── *.sh              # Скрипты управления
```

## 🔧 Основные настройки

### Переменные окружения (.env):
```env
# Telegram Bot
TOKEN=your_telegram_bot_token
GROUP_ID=your_telegram_group_id

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# База данных
DB_PASSWORD=44_assistent_l44
DB_URL=postgresql+asyncpg://assistent:44_assistent_l44@postgres:5432/english

# Время уроков
TIMEZONE=Asia/Shanghai
LESSON_TIME=12:00

# Тестовый режим
TEST_MODE=true
TEST_INTERVAL_MINUTES=6
```

## 🎮 Команды бота

- `/start` - Начать работу с ботом
- `/test_scheduler` - Тестирование планировщика
- `/dev_mode` - Проверка режима разработки
- `/status` - Статус бота и настроек

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в правильности переменных окружения
3. Проверьте подключение к OpenAI API
4. Проверьте подключение к базе данных
5. Убедитесь что файл `database/init.sql` создан и настроен правильно
6. Используйте команду `/status` для диагностики

---

**English Assistant Bot** - ваш персональный AI-учитель английского языка! 🎓✨
