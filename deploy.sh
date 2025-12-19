#!/bin/bash
# Скрипт синхронизации и деплоя на сервер
# Использование: ./deploy.sh

set -e

# Конфигурация
SERVER_IP="${SERVER_IP:-188.68.221.90}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PATH="${SERVER_PATH:-/root/progressus}"
SSH_KEY="${SSH_KEY:-ssh/new}"
SKIP_MIGRATIONS="${SKIP_MIGRATIONS:-false}"
SKIP_BACKUP="${SKIP_BACKUP:-false}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Деплой Progressus Bot на сервер${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Проверяем наличие SSH ключа
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Ошибка: SSH ключ не найден: $SSH_KEY${NC}"
    exit 1
fi

# Устанавливаем права на SSH ключ
chmod 600 "$SSH_KEY"

# Проверяем подключение к серверу
echo -e "${YELLOW}[1/6] Проверка подключения к серверу...${NC}"
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 "${SERVER_USER}@${SERVER_IP}" "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Подключение успешно${NC}"
else
    echo -e "${RED}✗ Ошибка подключения к серверу${NC}"
    exit 1
fi

# Создаем бэкап на сервере (если не пропущен)
if [ "$SKIP_BACKUP" != "true" ]; then
    echo ""
    echo -e "${YELLOW}[2/6] Создание бэкапа на сервере...${NC}"
    BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
        "mkdir -p $SERVER_PATH/backups && \
         cd $SERVER_PATH && \
         docker compose exec -T postgres pg_dump -U progressus progressusbot > backups/backup_${BACKUP_DATE}.sql 2>/dev/null || \
         echo 'Бэкап БД пропущен (возможно, контейнер не запущен)'"
    echo -e "${GREEN}✓ Бэкап создан${NC}"
fi

# Синхронизация файлов
echo ""
echo -e "${YELLOW}[3/6] Синхронизация файлов с сервером...${NC}"

# Исключаем ненужные файлы и папки
# Note: rsync patterns - use / for directory separator, * matches any path component
EXCLUDE_PATTERNS=(
    "__pycache__/"
    "*/__pycache__/"
    "**/__pycache__/"
    "*.pyc"
    "*/*.pyc"
    "**/*.pyc"
    "*.pyo"
    "*/*.pyo"
    "**/*.pyo"
    "*.pyd"
    "*/*.pyd"
    "**/*.pyd"
    ".git/"
    ".gitignore"
    ".env"
    "*.log"
    "logs/"
    "docs/"
    "_static/"
    "_templates/"
    "backups/"
    ".idea/"
    ".vscode/"
    "*.swp"
    "*.swo"
    "*~"
    ".DS_Store"
    "ssh/"
    "description_before_start_and_commands.png"
    "CJM.uml"
)

# Создаем временный файл с исключениями
EXCLUDE_FILE=$(mktemp)
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    echo "$pattern" >> "$EXCLUDE_FILE"
done

# Синхронизируем файлы через rsync
echo -e "${GRAY}Выполняется rsync...${NC}"
rsync -avz --delete --exclude-from="$EXCLUDE_FILE" \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    ./ "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/"

# Удаляем временный файл
rm -f "$EXCLUDE_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Файлы синхронизированы${NC}"
else
    echo -e "${RED}✗ Ошибка синхронизации файлов${NC}"
    exit 1
fi

# Останавливаем контейнеры
echo ""
echo -e "${YELLOW}[4/6] Остановка контейнеров на сервере...${NC}"
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
    "cd $SERVER_PATH && docker compose down"; then
    echo -e "${GREEN}✓ Контейнеры остановлены${NC}"
else
    echo -e "${YELLOW}⚠ Предупреждение: Не удалось остановить контейнеры (возможно, они уже остановлены)${NC}"
fi

# Применяем миграции (если не пропущены)
if [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo ""
    echo -e "${YELLOW}[5/6] Применение миграций БД...${NC}"
    
    # Сначала запускаем контейнеры в фоне для миграций
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
        "cd $SERVER_PATH && docker compose up -d postgres redis"
    
    # Ждем готовности БД
    echo -e "${GRAY}Ожидание готовности БД...${NC}"
    sleep 5
    
    # Применяем миграции
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
        "cd $SERVER_PATH && docker compose run --rm bot python -m alembic upgrade head"; then
        echo -e "${GREEN}✓ Миграции применены${NC}"
    else
        echo -e "${YELLOW}⚠ Предупреждение: Ошибка при применении миграций${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}[5/6] Применение миграций пропущено (SKIP_MIGRATIONS=true)${NC}"
fi

# Перезапускаем контейнеры
echo ""
echo -e "${YELLOW}[6/6] Перезапуск контейнеров на сервере...${NC}"
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
    "cd $SERVER_PATH && docker compose up --build -d"; then
    echo -e "${GREEN}✓ Контейнеры перезапущены${NC}"
else
    echo -e "${RED}✗ Ошибка при перезапуске контейнеров${NC}"
    exit 1
fi

# Проверяем статус контейнеров
echo ""
echo -e "${YELLOW}Проверка статуса контейнеров...${NC}"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
    "cd $SERVER_PATH && docker compose ps"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}  Деплой завершен успешно!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${YELLOW}Для просмотра логов используйте:${NC}"
echo -e "${GRAY}  ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP} 'cd $SERVER_PATH && docker compose logs -f bot'${NC}"
echo ""

