# Progressusbot - MVP Telegram бот для личного развития

Telegram-бот для личного развития по трём направлениям: заработок, здоровье, ментальное состояние.

## Технологический стек

- **Python 3.12**
- **aiogram 3.22.0** - async Telegram Bot API
- **FastAPI 0.115.0** - webhook сервер
- **PostgreSQL 16** - база данных
- **Redis 7.4** - FSM storage и Celery broker
- **OpenRouter API** - GPT-4o-mini через OpenRouter для персонализации
- **Celery 5.4.0** - фоновые задачи (напоминания, ежедневные ДЗ)
- **YooKassa 3.0.0** - платежная система
- **Yandex SpeechKit** - распознавание голосовых сообщений
- **Docker Compose** - деплой и оркестрация

## Функционал

### Основные возможности

- ✅ **Расширенный опросник** для глубокого понимания пользователя:
  - 5 базовых вопросов (пол, возраст, имя, 3 ценности, сферы развития)
  - 5 персонализированных развернутых вопросов от GPT на основе ответов
  - Выбор ролевой модели (5 вариантов)
  - Цель на 3 месяца
- ✅ **Автоматическая генерация роадмапа** достижения цели с 4 этапами (недели 1-2, 3-4, 5-8, 9-12)
- ✅ **Персонализированные задания** на основе роадмапа, опыта и целей пользователя
- ✅ **Система уровней (0-10)** с прогрессом
- ✅ **Умная проверка ДЗ**:
  - Если выполнено хорошо → новое ДЗ для следующего уровня
  - Если выполнено плохо → конкретные правки к текущему ДЗ с четкими инструкциями
- ✅ **Голосовые сообщения** - распознавание через Yandex SpeechKit
- ✅ **Персонализация** - глубокие вопросы для лучшего понимания пользователя
- ✅ **Платежи через YooKassa** (299 руб за premium)
- ✅ **Реферальная система** - за 3 оплативших реферала месяц Premium в подарок
- ✅ **Согласие на обработку персональных данных**
- ✅ **Админ панель** - генерация Excel отчетов по пользователям
- ✅ **Celery задачи** - ежедневные напоминания и отправка ДЗ

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone <repository_url>
cd progressus
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_from_botfather
BOT_USERNAME=your_bot_username

# OpenRouter API
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openai/gpt-4o-mini

# Database
DB_URL=postgresql+asyncpg://progressus:progressus_password@postgres:5432/progressusbot

# Redis
REDIS_URL=redis://redis:6379/0

# Payments (YooKassa)
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
YOOKASSA_WEBHOOK_URL=https://your-domain.com/yookassa/webhook

# Yandex SpeechKit (для голосовых сообщений)
YANDEX_SPEECHKIT_API_KEY=your_speechkit_key

# Webhook (оставь пустым для polling режима)
WEBHOOK_URL=https://your-domain.com/webhook
WEBHOOK_SECRET=your_webhook_secret

# Privacy Policy
PRIVACY_POLICY_URL=https://your-domain.com/oferta

# Environment
ENVIRONMENT=development  # или production
```

**Примечание:** Если `WEBHOOK_URL` оставить пустым, бот автоматически переключится в **polling режим** (бот сам опрашивает Telegram на наличие новых сообщений). Это удобно для локальной разработки без настройки домена и HTTPS.

### 3. Запуск через Docker Compose

```bash
docker compose up -d
```

Это запустит:
- PostgreSQL на порту 5432
- Redis на порту 6379
- FastAPI бот на порту 8000
- Celery worker для фоновых задач

### 4. Режимы работы бота

**Polling режим (по умолчанию, если WEBHOOK_URL пустой):**
- Бот автоматически опрашивает Telegram на наличие новых сообщений
- Не требует публичного URL или HTTPS
- Подходит для локальной разработки
- Просто оставь `WEBHOOK_URL=` пустым в `.env`

**Webhook режим (для production):**
- Требует публичный HTTPS URL
- Более эффективен для production
- Установи `WEBHOOK_URL` в `.env`
- После запуска бота webhook установится автоматически
- Или установи вручную:
  ```bash
  curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://your-domain.com/webhook&secret_token=<WEBHOOK_SECRET>"
  ```

### 5. Миграции БД

**Важно:** Перед первым запуском необходимо применить миграции для создания таблиц в БД.

Миграции Alembic выполняются автоматически при первом запуске через `Base.metadata.create_all()`, но рекомендуется применить их вручную:

```bash
# Через Docker
docker compose run --rm bot python -m alembic upgrade head

# Или локально (если alembic установлен)
alembic upgrade head
```

**Доступные миграции:**
- `001_add_new_survey_fields.py` - Расширенные поля опросника
- `002_add_premium_expires_at.py` - Дата окончания premium
- `003_add_survey_state.py` - Сохранение состояния опроса
- `004_add_consultation_used.py` - Флаг использования консультации
- `005_add_personalization_data.py` - Данные персонализации

## Структура проекта

```
progressus/
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD для автоматического деплоя
├── app/
│   ├── handlers/                   # Обработчики команд и сообщений
│   │   ├── start.py                # Обработка /start
│   │   ├── survey.py               # Опросник (базовые и детальные вопросы)
│   │   ├── reports.py              # Обработка отчетов по ДЗ
│   │   ├── privacy.py              # Согласие на обработку ПД
│   │   ├── restart.py              # Рестарт бота (/restart)
│   │   ├── referral.py             # Реферальная система (/ref)
│   │   ├── payments.py             # Оплата premium через YooKassa
│   │   ├── menu.py                 # Главное меню
│   │   ├── voice.py                # Обработка голосовых сообщений
│   │   └── personalization.py      # Персонализация (глубокие вопросы)
│   ├── services/                   # Бизнес-логика
│   │   ├── user_service.py         # Работа с пользователями
│   │   ├── referral_service.py    # Реферальная система
│   │   ├── survey_state_service.py # Сохранение состояния опроса
│   │   ├── report_generator.py    # Генерация Excel отчетов
│   │   └── yookassa_service.py    # Интеграция с YooKassa
│   ├── middleware/                 # Middleware
│   │   └── rate_limit.py          # Rate limiting для защиты от спама
│   ├── prompts/                    # Промпты для GPT
│   │   ├── personalities/       # Промпты ролевых моделей (5 вариантов)
│   │   │   ├── andrew_tate.py
│   │   │   ├── grebenyuk.py
│   │   │   ├── khabib.py
│   │   │   ├── oleg_tinkov.py
│   │   │   └── tyler_durden.py
│   │   ├── system.py              # Системный промпт для модели пользователя
│   │   ├── homework_analysis.py   # Промпт для анализа ДЗ
│   │   └── code_examples.py       # Примеры использования
│   ├── templates/                  # HTML шаблоны
│   │   ├── admin.html             # Админ панель
│   │   └── oferta.html            # Публичная оферта
│   ├── config.py                  # Конфигурация (загрузка .env)
│   ├── database.py                # Подключение к БД (SQLAlchemy)
│   ├── models.py                  # SQLAlchemy модели (User, Survey, Report, Payment)
│   ├── states.py                  # FSM состояния для опросника
│   ├── keyboards.py              # Inline клавиатуры
│   ├── gpt.py                     # OpenRouter API клиент
│   └── main.py                    # FastAPI приложение (webhook/polling)
├── celery_app/                    # Celery задачи
│   ├── celery_worker.py          # Конфигурация Celery
│   └── tasks.py                  # Фоновые задачи (напоминания, ДЗ)
├── migrations/                    # Alembic миграции
│   ├── env.py
│   └── versions/                 # Версии миграций БД
├── logs/                          # Логи приложения
├── reports/                       # Сгенерированные Excel отчеты
├── docker-compose.yml             # Docker Compose конфигурация
├── docker-compose.override.yml     # Override для локальной разработки (не коммитится)
├── Dockerfile                     # Docker образ бота
├── requirements.txt               # Python зависимости
├── .env.dev.example               # Шаблон .env для dev окружения
├── deploy.ps1                     # Скрипт деплоя для Windows
├── deploy.sh                      # Скрипт деплоя для Linux/Mac
├── DEPLOY.md                      # Инструкция по деплою
├── DEV_SETUP.md                   # Инструкция по настройке dev окружения
└── README.md                      # Этот файл
```

## Команды бота

- `/start` - Начало работы, запуск опросника
- `/menu` - Главное меню
- `/report` - Отправка отчета по выполненному ДЗ (можно просто отправить текст отчета)
- `/ref` или `/referral` - Получение реферальной ссылки
- `/restart` - Рестарт бота (сброс данных и повторный опрос)

## Workflow пользователя

1. **Приветствие** → Согласие на обработку ПД
2. **5 базовых вопросов**: пол → возраст → имя → 3 ценности → сферы развития
3. **5 развернутых вопросов** от GPT (генерируются на основе базовых ответов)
4. **Выбор ролевой модели** (5 вариантов)
5. **Ввод цели на 3 месяца**
6. **Генерация роадмапа** с 4 этапами достижения цели
7. **Получение первого ДЗ** уровня 0, соответствующего первому этапу роадмапа
8. **Выполнение ДЗ → Отчет → Оценка**:
   - ✅ Хорошо → Новое ДЗ для следующего уровня
   - ⚠️ Плохо → Правки к текущему ДЗ с конкретными инструкциями
9. **Цикл**: Новое ДЗ → Отчет → Оценка → ...
10. **Персонализация** - дополнительные вопросы для лучшего понимания
11. **Голосовые сообщения** - можно отвечать голосом (распознавание через Yandex SpeechKit)

## Ролевые модели

Бот поддерживает 5 ролевых моделей, каждая со своим стилем общения:

1. **Эндрю Тейт** (`andrew_tate`) - Прямолинейный, агрессивный, фокус на деньгах и власти
2. **Михаил Гребенюк** (`grebenyuk`) - Энергичный, ироничный, фокус на выходе из зоны комфорта
3. **Хабиб Нурмагомедов** (`khabib`) - Спокойный, духовный, фокус на дисциплине и семье
4. **Олег Тиньков** (`oleg_tinkov`) - Практичный, результат-ориентированный, фокус на предпринимательстве
5. **Тайлер Дёрден** (`tyler_durden`) - Философский, провокационный, фокус на свободе и разрушении системы

Каждая модель имеет свой системный промпт и стиль общения, который влияет на генерацию заданий и обратную связь.

## Платежи

Бот интегрирован с **YooKassa** для приема платежей:

- Цена premium доступа: **299 руб**
- При успешной оплате автоматически активируется premium на 1 месяц
- Webhook от YooKassa обрабатывается автоматически
- При первой оплате уровень пользователя повышается до 1

**Реферальная система:**
- За 3 оплативших реферала реферер получает месяц бесплатного Premium
- Реферальная ссылка доступна через `/ref`

## Админ панель

Доступна админ панель для генерации отчетов:

- **URL:** `https://your-domain.com/admin`
- **Функционал:** Генерация Excel отчетов по пользователям за указанный период
- **Данные:** ID пользователя, имя, уровень, premium статус, дата регистрации и т.д.

## Celery задачи

Фоновые задачи для автоматизации:

- **`send_daily_homework`** - Отправка ежедневного ДЗ premium пользователям
- **`send_reminder`** - Напоминание об отчете, если не было отчета 2+ дня
- **`schedule_daily_tasks`** - Планирование ежедневных задач (требует настройки cron)

## Разработка

### Локальный запуск без Docker

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите PostgreSQL и Redis локально

3. Примените миграции БД:
```bash
python -m alembic upgrade head
```

4. Запустите бота:
```bash
python -m app.main
```

5. Запустите Celery worker (опционально, для фоновых задач):
```bash
celery -A celery_app.celery_worker worker --loglevel=info
```

### Тестирование в dev ветке

Для тестирования изменений используйте dev ветку с локальным запуском через polling.

**Быстрый старт:**
1. Переключитесь на ветку `dev`: `git checkout dev`
2. Создайте `.env.dev` из `.env.dev.example`: `cp .env.dev.example .env.dev`
3. Заполните необходимые переменные в `.env.dev`
4. Запустите: `docker compose --env-file .env.dev up --build`

**Особенности dev окружения:**
- ✅ Работает в polling режиме (не требует webhook)
- ✅ Отдельная БД `progressusbot_dev` (не пересекается с production)
- ✅ Отдельный Redis DB `1` (не пересекается с production)
- ✅ Используется тестовый бот с отдельным токеном

Подробная инструкция в [`DEV_SETUP.md`](DEV_SETUP.md).

### Переменные окружения

**Важно:** Файл `.env` не синхронизируется при деплое через CI/CD. Если нужно изменить переменные на production сервере, сделайте это вручную через SSH:

```bash
ssh -i ssh/new root@188.68.221.90
cd /root/progressus
nano .env  # или vim .env
docker compose restart bot celery
```

## CI/CD - Автоматический деплой

Проект настроен с автоматическим деплоем через GitHub Actions. При каждом push в ветку `main` автоматически выполняется деплой на production сервер.

### Настройка CI/CD

1. Добавьте секреты в GitHub: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

2. Добавьте следующие секреты:
   - **`SSH_PRIVATE_KEY`** - содержимое файла `ssh/new` (весь ключ, включая `-----BEGIN...` и `-----END...`)
   - **`SERVER_IP`** → `188.68.221.90`
   - **`SERVER_USER`** → `root`
   - **`SERVER_PATH`** → `/root/progressus`

3. При push в `main` автоматически запустится деплой

### Что делает CI/CD

1. ✅ Создает бэкап БД (сохраняется в `/root/progressus/backups/`)
2. 📦 Синхронизирует файлы на сервер через rsync
3. 🛑 Останавливает Docker контейнеры
4. 🔄 Применяет миграции БД
5. 🚀 Перезапускает контейнеры с новым кодом
6. ✅ Проверяет статус контейнеров

### Ручной деплой

Для ручного деплоя используйте скрипты:
- **Windows:** `.\deploy.ps1`
- **Linux/Mac:** `./deploy.sh`

Подробнее в [`DEPLOY.md`](DEPLOY.md).

## Бэкапы

Бэкапы базы данных автоматически создаются при каждом деплое и сохраняются в:

```
/root/progressus/backups/backup_YYYYMMDD_HHMMSS.sql
```

**Восстановление из бэкапа:**
```bash
cd /root/progressus
docker compose exec -T postgres psql -U progressus progressusbot < backups/backup_20260112_191500.sql
```

## Логи

Логи пишутся в `logs/app.log` и выводятся в консоль.

**Просмотр логов через Docker:**
```bash
docker compose logs -f bot
docker compose logs -f celery
```

## Лицензия

MIT
