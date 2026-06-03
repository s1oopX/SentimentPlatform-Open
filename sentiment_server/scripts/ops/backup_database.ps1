#Requires -Version 5.1
<#
.SYNOPSIS
    定期数据库备份脚本（满足任务书"每周至少备份 1 次"要求）

.DESCRIPTION
    使用 mysqldump 导出 sentiment_analysis 数据库，保存到 backups/ 目录。
    文件名包含时间戳，自动清理超过 30 天的旧备份。

.EXAMPLE
    # 手动执行
    .\scripts\ops\backup_database.ps1

    # Windows 任务计划程序（每周日凌晨 2 点）
    # 操作: powershell.exe
    # 参数: -ExecutionPolicy Bypass -File "D:\code\SentimentPlatform\sentiment_server\scripts\ops\backup_database.ps1"
#>

param(
    [string]$DbHost = '127.0.0.1',
    [int]$DbPort = 3306,
    [string]$DbUser = 'root',
    [string]$DbPassword = '123456',
    [string]$DbName = 'sentiment_analysis',
    [int]$RetentionDays = 30
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$backupDir = Join-Path $scriptRoot 'backups'

# 确保备份目录存在
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

# 检查 mysqldump 是否可用
$mysqldump = Get-Command 'mysqldump' -ErrorAction SilentlyContinue
if (-not $mysqldump) {
    Write-Error "mysqldump 未找到，请确保 MySQL 客户端工具已安装并在 PATH 中"
    exit 1
}

# 生成备份文件名
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupFile = Join-Path $backupDir "数据库备份_${timestamp}.sql"

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 开始备份数据库 $DbName ..." -ForegroundColor Cyan

# 执行备份
$env:MYSQL_PWD = $DbPassword
try {
    & mysqldump --user=$DbUser --host=$DbHost --port=$DbPort --default-character-set=utf8mb4 $DbName > $backupFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "mysqldump 执行失败 (exit code: $LASTEXITCODE)"
        exit 1
    }
} finally {
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
}

$fileSize = (Get-Item $backupFile).Length
$fileSizeMB = [math]::Round($fileSize / 1MB, 2)
Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 备份完成: $backupFile ($fileSizeMB MB)" -ForegroundColor Green

# 清理过期备份
$cutoff = (Get-Date).AddDays(-$RetentionDays)
$expiredFiles = @(
    Get-ChildItem $backupDir -Filter '数据库备份_*.sql'
    Get-ChildItem $backupDir -Filter 'backup_*.sql'
) | Where-Object { $_.LastWriteTime -lt $cutoff }
if ($expiredFiles) {
    $expiredFiles | Remove-Item -Force
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 已清理 $($expiredFiles.Count) 个过期备份（超过 $RetentionDays 天）" -ForegroundColor Yellow
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 备份任务完成" -ForegroundColor Green
