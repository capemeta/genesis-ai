# 安装项目依赖
# PowerShell 脚本

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "Genesis AI Platform - 依赖安装" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

# 检查 uv 是否安装
Write-Host "检查 uv 是否已安装..." -ForegroundColor Yellow
$uvInstalled = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvInstalled) {
    Write-Host "❌ uv 未安装" -ForegroundColor Red
    Write-Host ""
    Write-Host "请先安装 uv:" -ForegroundColor Yellow
    Write-Host "  方法 1: 使用 pip" -ForegroundColor Cyan
    Write-Host "    pip install uv" -ForegroundColor White
    Write-Host ""
    Write-Host "  方法 2: 使用官方安装脚本" -ForegroundColor Cyan
    Write-Host "    powershell -c `"irm https://astral.sh/uv/install.ps1 | iex`"" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✅ uv 已安装" -ForegroundColor Green
Write-Host ""

# 同步依赖
Write-Host "正在同步项目依赖..." -ForegroundColor Yellow
Write-Host ""

try {
    uv sync
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "=" -NoNewline -ForegroundColor Cyan
        Write-Host ("=" * 59) -ForegroundColor Cyan
        Write-Host "✅ 依赖安装成功！" -ForegroundColor Green
        Write-Host "=" -NoNewline -ForegroundColor Cyan
        Write-Host ("=" * 59) -ForegroundColor Cyan
        Write-Host ""
        Write-Host "已安装的主要依赖:" -ForegroundColor Yellow
        Write-Host "  • FastAPI - Web 框架" -ForegroundColor White
        Write-Host "  • SQLAlchemy - ORM" -ForegroundColor White
        Write-Host "  • Redis - 缓存和速率限制" -ForegroundColor White
        Write-Host "  • Pillow - 验证码图片生成" -ForegroundColor White
        Write-Host "  • python-jose - JWT 令牌" -ForegroundColor White
        Write-Host "  • passlib - 密码哈希" -ForegroundColor White
        Write-Host "  • httpx - HTTP 客户端" -ForegroundColor White
        Write-Host ""
        Write-Host "下一步:" -ForegroundColor Yellow
        Write-Host "  1. 配置环境变量 (.env)" -ForegroundColor Cyan
        Write-Host "  2. 启动数据库和 Redis" -ForegroundColor Cyan
        Write-Host "  3. 运行应用: uv run uvicorn main:app --reload" -ForegroundColor Cyan
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "❌ 依赖安装失败" -ForegroundColor Red
        Write-Host ""
        Write-Host "请检查错误信息并重试" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "❌ 发生错误: $_" -ForegroundColor Red
    exit 1
}
