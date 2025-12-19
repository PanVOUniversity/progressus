# Инструкция по деплою на сервер

Скрипты автоматизируют процесс синхронизации файлов и деплоя бота на сервер.

## Доступные скрипты

- **`deploy.ps1`** - для Windows (PowerShell)
- **`deploy.sh`** - для Linux/Mac (Bash)

## Быстрый старт

### Windows (PowerShell)

```powershell
.\deploy.ps1
```

### Linux/Mac (Bash)

```bash
chmod +x deploy.sh
./deploy.sh
```

## Параметры

### PowerShell (deploy.ps1)

```powershell
# Базовый деплой
.\deploy.ps1

# С пропуском миграций
.\deploy.ps1 -SkipMigrations

# С пропуском бэкапа
.\deploy.ps1 -SkipBackup

# Кастомный сервер
.\deploy.ps1 -ServerIP "192.168.1.100" -ServerUser "admin" -ServerPath "/opt/progressus"
```

### Bash (deploy.sh)

```bash
# Базовый деплой
./deploy.sh

# С пропуском миграций
SKIP_MIGRATIONS=true ./deploy.sh

# С пропуском бэкапа
SKIP_BACKUP=true ./deploy.sh

# Кастомный сервер
SERVER_IP="192.168.1.100" SERVER_USER="admin" SERVER_PATH="/opt/progressus" ./deploy.sh
```

## Что делает скрипт

1. **Проверка подключения** - проверяет доступность сервера
2. **Создание бэкапа** - создает резервную копию БД (можно пропустить флагом)
3. **Синхронизация файлов** - копирует измененные файлы на сервер через rsync/scp
4. **Остановка контейнеров** - останавливает текущие Docker контейнеры
5. **Применение миграций** - применяет миграции БД (можно пропустить флагом)
6. **Перезапуск контейнеров** - пересобирает и запускает контейнеры с новыми изменениями

## Исключаемые файлы

Скрипт автоматически исключает из синхронизации:
- `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`
- `.git/`, `.gitignore`
- `.env` файлы
- `*.log`, `logs/`
- `docs/`, `_static/`, `_templates/`
- `backups/`
- `.idea/`, `.vscode/`
- `ssh/` (SSH ключи)
- `description_before_start_and_commands.png`, `CJM.uml`

## Требования

### Windows
- PowerShell 5.1+
- SSH клиент (обычно встроен в Windows 10+)
- rsync (опционально, для более эффективной синхронизации)
  - Можно установить через [Cygwin](https://www.cygwin.com/) или [Git for Windows](https://git-scm.com/download/win)

### Linux/Mac
- Bash
- SSH клиент
- rsync (обычно предустановлен)

## Настройка SSH ключа

По умолчанию скрипт использует ключ `ssh/new`. Убедитесь, что:
1. Ключ существует и имеет правильные права доступа
2. Публичный ключ добавлен на сервер в `~/.ssh/authorized_keys`

Для Linux/Mac установите права:
```bash
chmod 600 ssh/new
```

## Проверка статуса после деплоя

После деплоя можно проверить логи:

```bash
ssh -i ssh/new root@188.68.221.90 'cd /root/progressus && docker compose logs -f bot'
```

Или статус контейнеров:

```bash
ssh -i ssh/new root@188.68.221.90 'cd /root/progressus && docker compose ps'
```

## Устранение проблем

### Ошибка подключения к серверу
- Проверьте доступность сервера: `ping 188.68.221.90`
- Проверьте SSH ключ: `ssh -i ssh/new root@188.68.221.90`
- Убедитесь, что публичный ключ добавлен на сервер

### Ошибка синхронизации файлов
- Если rsync недоступен, скрипт автоматически использует scp
- Проверьте права доступа к файлам на сервере
- Убедитесь, что путь на сервере существует

### Ошибка при применении миграций
- Проверьте, что контейнеры postgres и redis запущены
- Проверьте логи: `docker compose logs postgres`
- Можно пропустить миграции флагом `-SkipMigrations` и применить вручную

### Ошибка при перезапуске контейнеров
- Проверьте логи: `docker compose logs`
- Убедитесь, что все переменные окружения настроены в `.env` на сервере
- Проверьте, что Docker и Docker Compose установлены на сервере

## Ручной деплой (если скрипт не работает)

```bash
# 1. Синхронизация файлов
rsync -avz --delete -e "ssh -i ssh/new" ./ root@188.68.221.90:/root/progressus/

# 2. Подключение к серверу
ssh -i ssh/new root@188.68.221.90

# 3. На сервере: остановка контейнеров
cd /root/progressus
docker compose down

# 4. Применение миграций (опционально)
docker compose up -d postgres redis
sleep 5
docker compose run --rm bot python -m alembic upgrade head

# 5. Перезапуск контейнеров
docker compose up --build -d

# 6. Проверка статуса
docker compose ps
docker compose logs -f bot
```

