# Script to clear Redis cache and PostgreSQL database on server
# Usage: .\clear_server_data.ps1

param(
    [string]$ServerIP = "188.68.221.90",
    [string]$ServerUser = "root",
    [string]$ServerPath = "/root/progressus",
    [string]$SSHKey = "ssh\new",
    [switch]$ClearRedis = $true,
    [switch]$ClearDatabase = $true,
    [switch]$Confirm = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Clear Server Cache and Database" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if SSH key exists
if (-not (Test-Path $SSHKey)) {
    Write-Host "Error: SSH key not found: $SSHKey" -ForegroundColor Red
    exit 1
}

# Check server connection
Write-Host "[1/4] Checking server connection..." -ForegroundColor Yellow
try {
    $testConnection = ssh -i $SSHKey -o StrictHostKeyChecking=no -o ConnectTimeout=5 "${ServerUser}@${ServerIP}" "echo 'OK'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to connect to server"
    }
    Write-Host "[OK] Connection successful" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Connection error: $_" -ForegroundColor Red
    exit 1
}

# Confirmation
if (-not $Confirm) {
    Write-Host ""
    Write-Host "WARNING: This will delete all data!" -ForegroundColor Red
    Write-Host "  - Redis cache will be cleared" -ForegroundColor Yellow
    Write-Host "  - PostgreSQL database will be cleared" -ForegroundColor Yellow
    Write-Host ""
    $confirmation = Read-Host "Type 'yes' to continue"
    if ($confirmation -ne "yes") {
        Write-Host "Operation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# Clear Redis cache
if ($ClearRedis) {
    Write-Host ""
    Write-Host "[2/4] Clearing Redis cache..." -ForegroundColor Yellow
    try {
        $redisCommand = 'cd ' + $ServerPath + ' && docker compose exec -T redis redis-cli FLUSHDB'
        ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $redisCommand
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Redis cache cleared" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Failed to clear Redis cache" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Error clearing Redis: $_" -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "[2/4] Redis clearing skipped" -ForegroundColor Yellow
}

# Clear PostgreSQL database
if ($ClearDatabase) {
    Write-Host ""
    Write-Host "[3/4] Clearing PostgreSQL database..." -ForegroundColor Yellow
    try {
        # Drop and recreate database
        $dbCommand = 'cd ' + $ServerPath + ' && docker compose exec -T postgres psql -U progressus -d postgres -c "DROP DATABASE IF EXISTS progressusbot;" && docker compose exec -T postgres psql -U progressus -d postgres -c "CREATE DATABASE progressusbot;"'
        ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $dbCommand
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] PostgreSQL database cleared and recreated" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Failed to clear PostgreSQL database" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Error clearing database: $_" -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "[3/4] Database clearing skipped" -ForegroundColor Yellow
}

# Restart containers to apply changes
Write-Host ""
Write-Host "[4/4] Restarting containers..." -ForegroundColor Yellow
try {
    $restartCommand = 'cd ' + $ServerPath + ' && docker compose restart bot celery'
    ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $restartCommand
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Containers restarted" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Failed to restart containers" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] Error restarting containers: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Operation completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: You may need to run migrations after clearing the database:" -ForegroundColor Yellow
Write-Host "  ssh -i $SSHKey ${ServerUser}@${ServerIP} 'cd $ServerPath && docker compose run --rm bot python -m alembic upgrade head'" -ForegroundColor Gray
Write-Host ""

