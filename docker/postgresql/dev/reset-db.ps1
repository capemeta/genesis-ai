param(
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$postgresqlDir = Split-Path -Parent $scriptDir
$dataDir = Join-Path $postgresqlDir "pgdata-dev"
$containerName = "genesis-ai-db-dev"
$databaseName = "genesis_ai"

function Invoke-Compose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        & docker-compose @Arguments
    }
    else {
        & docker compose @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "docker compose 命令执行失败：$($Arguments -join ' ')"
    }
}

function Wait-ForContainerHealthy {
    param(
        [string]$Name,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $Name 2>$null
        if ($LASTEXITCODE -eq 0) {
            $status = $status.Trim()
            if ($status -eq "healthy" -or $status -eq "running") {
                return
            }
        }

        Start-Sleep -Seconds 2
    }

    throw "等待容器 $Name 就绪超时。"
}

Set-Location $scriptDir

Write-Host "=========================================="
Write-Host "Genesis AI - 开发环境强制重建数据库"
Write-Host "=========================================="
Write-Host ""
Write-Host "将删除的数据目录：$dataDir"
Write-Host "目标容器：$containerName"
Write-Host "目标数据库：$databaseName"
Write-Host ""

if (-not $Force) {
    $confirmation = Read-Host "此操作会永久删除开发数据库数据。请输入 RESET $databaseName 继续"
    if ($confirmation -ne "RESET $databaseName") {
        throw "确认串不匹配，已取消强制重建。"
    }
}

# 先停容器，再删除数据目录，确保不会误删正在使用的数据文件。
Write-Host ""
Write-Host "1. 停止开发环境容器..."
Invoke-Compose down --remove-orphans

if (Test-Path $dataDir) {
    Write-Host ""
    Write-Host "2. 删除旧数据目录..."
    Remove-Item -Path $dataDir -Recurse -Force
}
else {
    Write-Host ""
    Write-Host "2. 数据目录不存在，跳过删除。"
}

Write-Host ""
Write-Host "3. 重新启动开发环境容器..."
Invoke-Compose up -d

Write-Host ""
Write-Host "4. 等待 PostgreSQL 就绪..."
Wait-ForContainerHealthy -Name $containerName

Write-Host ""
Write-Host "开发环境数据库已强制重建完成（已自动导入 init-schema.sql）。"
