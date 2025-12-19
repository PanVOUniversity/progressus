# Deployment script for syncing and deploying to server
# Usage: .\deploy.ps1

param(
    [string]$ServerIP = "188.68.221.90",
    [string]$ServerUser = "root",
    [string]$ServerPath = "/root/progressus",
    [string]$SSHKey = "ssh\new",
    [switch]$SkipMigrations = $false,
    [switch]$SkipBackup = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploying Progressus Bot to Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if SSH key exists
if (-not (Test-Path $SSHKey)) {
    Write-Host "Error: SSH key not found: $SSHKey" -ForegroundColor Red
    exit 1
}

# Check server connection
Write-Host "[1/6] Checking server connection..." -ForegroundColor Yellow
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

# Create backup on server (if not skipped)
if (-not $SkipBackup) {
    Write-Host ""
    Write-Host "[2/6] Creating backup on server..." -ForegroundColor Yellow
    $backupDate = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupCommand = 'mkdir -p ' + $ServerPath + '/backups && cd ' + $ServerPath + ' && docker compose exec -T postgres pg_dump -U progressus progressusbot > backups/backup_' + $backupDate + '.sql 2>/dev/null || echo "Database backup skipped (container may not be running)"'
    
    ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $backupCommand
    Write-Host "[OK] Backup created" -ForegroundColor Green
}

# Sync files
Write-Host ""
Write-Host "[3/6] Syncing files to server..." -ForegroundColor Yellow

# Remove all .pyc files and __pycache__ directories before sync
Write-Host "Cleaning up .pyc files and __pycache__ directories..." -ForegroundColor Gray
Get-ChildItem -Path . -Recurse -Include "*.pyc", "*.pyo", "*.pyd" -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[OK] Cleanup completed" -ForegroundColor Green

# Exclude unnecessary files and folders
$excludePatterns = @(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".git",
    ".gitignore",
    ".env",
    "*.log",
    "logs",
    "docs",
    "_static",
    "_templates",
    "backups",
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
    "ssh",
    "description_before_start_and_commands.png",
    "CJM.uml",
    ".rsync_exclude"
)

# Create exclude file in current directory
$excludeFile = ".rsync_exclude"
$excludePatterns | ForEach-Object { Add-Content -Path $excludeFile -Value $_ }

Write-Host "Running rsync..." -ForegroundColor Gray
try {
    # Use rsync if available, otherwise scp
    $rsyncAvailable = Get-Command rsync -ErrorAction SilentlyContinue
    if ($rsyncAvailable) {
        # Build rsync command with exclude file and additional filters
        $rsyncCommand = "rsync -avz --delete --exclude-from=.rsync_exclude --filter='- *.pyc' --filter='- *.pyo' --filter='- *.pyd' --filter='- __pycache__/' -e `"ssh -i $SSHKey -o StrictHostKeyChecking=no`" ./ ${ServerUser}@${ServerIP}:${ServerPath}/"
        Invoke-Expression $rsyncCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Error syncing files"
        }
        # Clean up exclude file
        Remove-Item -Path $excludeFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "rsync not found, using scp..." -ForegroundColor Yellow
        # Clean up exclude file
        Remove-Item -Path $excludeFile -Force -ErrorAction SilentlyContinue
        # Alternative via scp (less efficient but works)
        $scpCommand = "scp -i $SSHKey -o StrictHostKeyChecking=no -r app celery_app migrations alembic.ini docker-compose.yml Dockerfile requirements.txt ${ServerUser}@${ServerIP}:${ServerPath}/"
        Invoke-Expression $scpCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Error copying files"
        }
    }
    Write-Host "[OK] Files synced" -ForegroundColor Green
} catch {
    # Clean up exclude file on error
    Remove-Item -Path $excludeFile -Force -ErrorAction SilentlyContinue
    Write-Host "[ERROR] Sync error: $_" -ForegroundColor Red
    exit 1
}

# Stop containers
Write-Host ""
Write-Host "[4/6] Stopping containers on server..." -ForegroundColor Yellow
$stopCommand = 'cd ' + $ServerPath + ' && docker compose down'
ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $stopCommand
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Failed to stop containers (they may already be stopped)" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Containers stopped" -ForegroundColor Green
}

# Apply migrations (if not skipped)
if (-not $SkipMigrations) {
    Write-Host ""
    Write-Host "[5/6] Applying database migrations..." -ForegroundColor Yellow
    
    # Start containers in background for migrations
    $startForMigrations = 'cd ' + $ServerPath + ' && docker compose up -d postgres redis'
    ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $startForMigrations
    
    # Wait for database readiness
    Write-Host "Waiting for database to be ready..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    
    # Apply migrations
    $migrateCommand = 'cd ' + $ServerPath + ' && docker compose run --rm bot python -m alembic upgrade head'
    ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $migrateCommand
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Migrations applied" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Error applying migrations" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "[5/6] Migrations skipped (-SkipMigrations)" -ForegroundColor Yellow
}

# Restart containers
Write-Host ""
Write-Host "[6/6] Restarting containers on server..." -ForegroundColor Yellow
$restartCommand = 'cd ' + $ServerPath + ' && docker compose up --build -d'
ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $restartCommand
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Error restarting containers" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Containers restarted" -ForegroundColor Green

# Check container status
Write-Host ""
Write-Host "Checking container status..." -ForegroundColor Yellow
$statusCommand = 'cd ' + $ServerPath + ' && docker compose ps'
ssh -i $SSHKey -o StrictHostKeyChecking=no "${ServerUser}@${ServerIP}" $statusCommand

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs, use:" -ForegroundColor Yellow
$logCommand = "ssh -i $SSHKey ${ServerUser}@${ServerIP} 'cd $ServerPath && docker compose logs -f bot'"
Write-Host "  $logCommand" -ForegroundColor Gray
Write-Host ""

