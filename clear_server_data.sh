#!/bin/bash
# Script to clear Redis cache and PostgreSQL database on server
# Usage: ./clear_server_data.sh

set -e

# Configuration
SERVER_IP="${SERVER_IP:-188.68.221.90}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PATH="${SERVER_PATH:-/root/progressus}"
SSH_KEY="${SSH_KEY:-ssh/new}"
CLEAR_REDIS="${CLEAR_REDIS:-true}"
CLEAR_DATABASE="${CLEAR_DATABASE:-true}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Clear Server Cache and Database${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Error: SSH key not found: $SSH_KEY${NC}"
    exit 1
fi

# Set permissions on SSH key
chmod 600 "$SSH_KEY"

# Check server connection
echo -e "${YELLOW}[1/4] Checking server connection...${NC}"
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 "${SERVER_USER}@${SERVER_IP}" "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connection successful${NC}"
else
    echo -e "${RED}✗ Connection error${NC}"
    exit 1
fi

# Confirmation
echo ""
echo -e "${RED}WARNING: This will delete all data!${NC}"
echo -e "${YELLOW}  - Redis cache will be cleared${NC}"
echo -e "${YELLOW}  - PostgreSQL database will be cleared${NC}"
echo ""
read -p "Type 'yes' to continue: " confirmation
if [ "$confirmation" != "yes" ]; then
    echo -e "${YELLOW}Operation cancelled.${NC}"
    exit 0
fi

# Clear Redis cache
if [ "$CLEAR_REDIS" = "true" ]; then
    echo ""
    echo -e "${YELLOW}[2/4] Clearing Redis cache...${NC}"
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
        "cd $SERVER_PATH && docker compose exec -T redis redis-cli FLUSHDB"; then
        echo -e "${GREEN}✓ Redis cache cleared${NC}"
    else
        echo -e "${YELLOW}⚠ Failed to clear Redis cache${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}[2/4] Redis clearing skipped${NC}"
fi

# Clear PostgreSQL database
if [ "$CLEAR_DATABASE" = "true" ]; then
    echo ""
    echo -e "${YELLOW}[3/4] Clearing PostgreSQL database...${NC}"
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
        "cd $SERVER_PATH && \
         docker compose exec -T postgres psql -U progressus -d postgres -c 'DROP DATABASE IF EXISTS progressusbot;' && \
         docker compose exec -T postgres psql -U progressus -d postgres -c 'CREATE DATABASE progressusbot;'"; then
        echo -e "${GREEN}✓ PostgreSQL database cleared and recreated${NC}"
    else
        echo -e "${YELLOW}⚠ Failed to clear PostgreSQL database${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}[3/4] Database clearing skipped${NC}"
fi

# Restart containers
echo ""
echo -e "${YELLOW}[4/4] Restarting containers...${NC}"
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" \
    "cd $SERVER_PATH && docker compose restart bot celery"; then
    echo -e "${GREEN}✓ Containers restarted${NC}"
else
    echo -e "${YELLOW}⚠ Failed to restart containers${NC}"
fi

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}  Operation completed!${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "${YELLOW}Note: You may need to run migrations after clearing the database:${NC}"
echo -e "${GRAY}  ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP} 'cd $SERVER_PATH && docker compose run --rm bot python -m alembic upgrade head'${NC}"
echo ""

