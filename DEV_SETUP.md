# Настройка dev окружения для тестирования

Этот документ описывает, как настроить локальное тестирование в ветке `dev`.

## Быстрый старт

### 1. Переключитесь на ветку dev

```bash
git checkout dev
```

### 2. Создайте .env.dev файл

```bash
cp .env.dev.example .env.dev
```

Отредактируйте `.env.dev` и заполните необходимые переменные. **Важно:** Тестовый токен бота уже указан в шаблоне.

### 3. Запустите через Docker Compose

```bash
# Используйте --env-file для загрузки .env.dev
docker compose --env-file .env.dev up --build
```

Или создайте алиас для удобства:

**PowerShell:**
```powershell
function docker-dev { docker compose --env-file .env.dev $args }
docker-dev up --build
```

**Bash:**
```bash
alias docker-dev='docker compose --env-file .env.dev'
docker-dev up --build
```

## Особенности dev окружения

### Polling режим

В dev окружении бот **всегда работает в polling режиме** (не требует webhook):
- `WEBHOOK_URL` должен быть пустым
- Бот сам опрашивает Telegram на наличие новых сообщений
- Не требует публичного URL или HTTPS

### Отдельная база данных

- **БД:** `progressusbot_dev` (отдельная от production)
- **Redis DB:** `1` (отдельная от production)
- Данные не пересекаются с production

### Hot reload (опционально)

Если хотите видеть изменения кода без пересборки контейнера, раскомментируйте в `docker-compose.override.yml`:

```yaml
bot:
  volumes:
    - .:/app  # Mount кода
```

**Внимание:** Это может замедлить работу, так как Python файлы будут синхронизироваться.

## Работа с ветками

### Workflow разработки

1. **Создайте feature ветку от dev:**
   ```bash
   git checkout dev
   git pull
   git checkout -b feature/my-feature
   ```

2. **Тестируйте локально:**
   ```bash
   docker compose --env-file .env.dev up
   ```

3. **Мерджите в dev:**
   ```bash
   git checkout dev
   git merge feature/my-feature
   git push origin dev
   ```

4. **После тестирования мерджите в main:**
   ```bash
   git checkout main
   git merge dev
   git push origin main
   # Автоматически запустится деплой в production
   ```

### CI/CD

- **Push в `dev`** → ничего не происходит (только локальное тестирование)
- **Push/merge в `main`** → автоматический деплой в production

## Тестовый бот

Используется отдельный тестовый бот с токеном:
```
8362210171:AAF8lF71xwRWtF6VKv6YQjJuaK794oxpydg
```

**Важно:** Не используйте production токен для тестирования!

## Остановка контейнеров

```bash
docker compose --env-file .env.dev down
```

Или с удалением volumes (очистка данных):

```bash
docker compose --env-file .env.dev down -v
```

## Миграции в dev

Применение миграций в dev окружении:

```bash
docker compose --env-file .env.dev run --rm bot python -m alembic upgrade head
```

## Логи

Просмотр логов dev бота:

```bash
docker compose --env-file .env.dev logs -f bot
docker compose --env-file .env.dev logs -f celery
```

## Отладка

### Подключение к контейнеру

```bash
docker compose --env-file .env.dev exec bot bash
```

### Проверка подключения к БД

```bash
docker compose --env-file .env.dev exec bot python -c "from app.database import engine; print('DB OK')"
```

### Проверка Redis

```bash
docker compose --env-file .env.dev exec redis redis-cli ping
```

## Устранение проблем

### Бот не отвечает

1. Проверьте логи: `docker compose --env-file .env.dev logs bot`
2. Убедитесь, что `WEBHOOK_URL` пустой в `.env.dev`
3. Проверьте токен бота

### Ошибка подключения к БД

1. Убедитесь, что контейнер postgres запущен: `docker compose --env-file .env.dev ps`
2. Проверьте `DB_URL` в `.env.dev`
3. Примените миграции

### Конфликт портов

Если порты 5432, 6379 или 8000 заняты, измените их в `docker-compose.override.yml`:

```yaml
postgres:
  ports:
    - "5433:5432"  # Измените внешний порт

redis:
  ports:
    - "6380:6379"

bot:
  ports:
    - "8001:8000"
```
