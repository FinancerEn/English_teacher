# 🐳 Документация Docker файлов

## 📁 Обзор файлов

В папке `docker/` находятся все файлы, необходимые для контейнеризации English Assistant Bot.

## 🏗️ Dockerfile

### Назначение:
Основной файл для создания Docker образа приложения.

### Содержимое:
```dockerfile
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаем директории для логов и временных файлов
RUN mkdir -p /app/logs /app/temp

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Запускаем приложение
CMD ["python", "app.py"]
```

### Объяснение слоев:

#### 1. Базовый образ:
```dockerfile
FROM python:3.11-slim
```
- Использует официальный Python 3.11 slim образ
- Минимальный размер, содержит только необходимые компоненты

#### 2. Системные зависимости:
```dockerfile
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*
```
- Устанавливает компиляторы для сборки Python пакетов
- Очищает кэш apt для уменьшения размера образа

#### 3. Рабочая директория:
```dockerfile
WORKDIR /app
```
- Устанавливает рабочую директорию `/app`

#### 4. Установка зависимостей:
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
- Копирует файл зависимостей
- Устанавливает Python пакеты без кэша

#### 5. Копирование кода:
```dockerfile
COPY . .
```
- Копирует весь код приложения в контейнер

#### 6. Создание директорий:
```dockerfile
RUN mkdir -p /app/logs /app/temp
```
- Создает директории для логов и временных файлов

#### 7. Безопасность:
```dockerfile
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser
```
- Создает непривилегированного пользователя
- Переключается на него для безопасности

#### 8. Запуск:
```dockerfile
CMD ["python", "app.py"]
```
- Команда по умолчанию для запуска приложения

## 🎯 docker-compose.yml

### Назначение:
Оркестрация контейнеров приложения и базы данных.

### Содержимое:
```yaml
version: '3.8'

services:
  english-bot:
    build: .
    container_name: english-bot
    restart: unless-stopped
    environment:
      - TOKEN=${TOKEN}
      - GROUP_ID=${GROUP_ID}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DB_URL=${DB_URL}
      - TIMEZONE=${TIMEZONE}
      - LESSON_TIME=${LESSON_TIME}
      - TEST_MODE=${TEST_MODE}
      - TEST_INTERVAL_MINUTES=${TEST_INTERVAL_MINUTES}
    depends_on:
      - postgres
    networks:
      - bot-network
    volumes:
      - ./logs:/app/logs
      - ./temp:/app/temp

  postgres:
    image: postgres:15
    container_name: english-bot-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=english_bot
      - POSTGRES_USER=bot_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - bot-network
    ports:
      - "5434:5432"

volumes:
  postgres_data:

networks:
  bot-network:
    driver: bridge
```

### Объяснение сервисов:

#### 1. english-bot (приложение):
```yaml
english-bot:
  build: .                    # Сборка из Dockerfile
  container_name: english-bot # Имя контейнера
  restart: unless-stopped     # Автоперезапуск
  environment:                # Переменные окружения
    - TOKEN=${TOKEN}
    - GROUP_ID=${GROUP_ID}
    # ... другие переменные
  depends_on:                 # Зависимости
    - postgres
  networks:                   # Сеть
    - bot-network
  volumes:                    # Монтирование томов
    - ./logs:/app/logs
    - ./temp:/app/temp
```

#### 2. postgres (база данных):
```yaml
postgres:
  image: postgres:15          # Официальный образ PostgreSQL
  container_name: english-bot-postgres
  restart: unless-stopped
  environment:                # Переменные БД
    - POSTGRES_DB=english_bot
    - POSTGRES_USER=bot_user
    - POSTGRES_PASSWORD=${DB_PASSWORD}
  volumes:                    # Тома данных
    - postgres_data:/var/lib/postgresql/data
    - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
  networks:
    - bot-network
  ports:                      # Проброс портов
    - "5434:5432"
```

### Тома и сети:

#### Тома:
```yaml
volumes:
  postgres_data:              # Постоянное хранение данных БД
```

#### Сети:
```yaml
networks:
  bot-network:                # Изолированная сеть
    driver: bridge
```

## 📝 env.example

### Назначение:
Пример файла с переменными окружения.

### Содержимое:
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

# Тестовый режим (false для продакшена)
TEST_MODE=false
TEST_INTERVAL_MINUTES=10
```

### Объяснение переменных:

#### Telegram Bot:
- `TOKEN` - токен бота от @BotFather
- `GROUP_ID` - ID группы для отчетов

#### OpenAI API:
- `OPENAI_API_KEY` - ключ API OpenAI

#### База данных:
- `DB_PASSWORD` - пароль для пользователя БД
- `DB_URL` - строка подключения к БД

#### Время уроков:
- `TIMEZONE` - часовой пояс
- `LESSON_TIME` - время ежедневных уроков

#### Режим работы:
- `TEST_MODE` - тестовый режим (true/false)
- `TEST_INTERVAL_MINUTES` - интервал в тестовом режиме

## 🗄️ database/init.sql

### Назначение:
Автоматическая инициализация базы данных при первом запуске.

### Основные функции:
1. **Создание пользователя и прав**
2. **Создание таблиц**
3. **Создание индексов**
4. **Загрузка начальных данных**

### Структура таблиц:

#### users (пользователи):
```sql
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    current_topic_id INTEGER,
    last_lesson_date TIMESTAMP,
    progress TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### topics (темы уроков):
```sql
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    tasks JSON,
    is_completed BOOLEAN DEFAULT FALSE
);
```

#### message_history (история сообщений):
```sql
CREATE TABLE IF NOT EXISTS message_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    voice_file_id VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### homeworks (домашние задания):
```sql
CREATE TABLE IF NOT EXISTS homeworks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    topic_id INTEGER REFERENCES topics(id),
    task_text TEXT NOT NULL,
    answer_text TEXT,
    is_checked BOOLEAN DEFAULT FALSE,
    date_assigned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_completed TIMESTAMP
);
```

## 🔧 Кастомизация

### Изменение портов:
```yaml
# docker-compose.yml
ports:
  - "5435:5432"  # Изменить 5434 на нужный порт
```

### Изменение версии Python:
```dockerfile
# Dockerfile
FROM python:3.12-slim  # Изменить версию
```

### Изменение версии PostgreSQL:
```yaml
# docker-compose.yml
postgres:
  image: postgres:16  # Изменить версию
```

### Добавление новых переменных окружения:
```yaml
# docker-compose.yml
environment:
  - NEW_VARIABLE=${NEW_VARIABLE}
```

```env
# env.example
NEW_VARIABLE=your_value_here
```

## 🔍 Отладка

### Просмотр логов сборки:
```bash
docker-compose build --no-cache --progress=plain
```

### Проверка переменных окружения:
```bash
docker-compose exec english-bot env
```

### Подключение к контейнеру:
```bash
docker-compose exec english-bot bash
```

### Проверка томов:
```bash
docker volume ls
docker volume inspect english-bot_postgres_data
```

## 📊 Мониторинг

### Статус контейнеров:
```bash
docker-compose ps
```

### Использование ресурсов:
```bash
docker stats
```

### Размер образов:
```bash
docker images
```

### Проверка сетей:
```bash
docker network ls
docker network inspect english-bot_bot-network
```

## 🛠 Устранение неполадок

### Проблемы сборки:
```bash
# Очистка кэша
docker system prune -a

# Принудительная пересборка
docker-compose build --no-cache
```

### Проблемы с томами:
```bash
# Проверка томов
docker volume ls

# Удаление томов
docker-compose down -v
```

### Проблемы с сетью:
```bash
# Проверка сети
docker network ls

# Пересоздание сети
docker-compose down
docker network prune
docker-compose up -d
```

## 📞 Поддержка

### Полезные команды:
```bash
# Информация о контейнерах
docker-compose config
docker-compose top

# Логи в реальном времени
docker-compose logs -f

# Остановка и удаление
docker-compose down
docker-compose down -v  # С удалением томов
```

### Контакты:
- Основная документация: `README.md`
- Документация скриптов: `SCRIPTS_GUIDE.md`
- Документация проекта: `../documentations/PROJECT_GUIDE.md`
