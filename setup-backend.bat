@echo off
chcp 65001 >nul
echo ================================================
echo    Genesis AI - 后端环境安装脚本
echo    将在 genesis-ai-platform 目录创建 .venv
echo ================================================
echo.

:: 检查是否在项目根目录
if not exist "genesis-ai-platform\pyproject.toml" (
    echo [错误] 未在项目根目录执行！
    echo 请在 genesis-ai 根目录运行此脚本
    pause
    exit /b 1
)

echo [1/5] 检查并安装 uv 包管理器...

:: 检查 uv 是否已安装
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo   未检测到 uv，正在通过 pip 安装...
    python -m pip install -U uv
    if %errorlevel% neq 0 (
        echo [错误] uv 安装失败，请手动安装 uv
        echo    推荐方式：winget install --id=astral-sh.uv -e
        pause
        exit /b 1
    )
    echo   uv 安装成功！
) else (
    echo   uv 已安装 ✓
)

echo.
echo [2/5] 进入 genesis-ai-platform 目录...
cd genesis-ai-platform

echo.
echo [3/5] 确保 Python 3.12 环境...
uv python pin 3.12
uv python install --quiet 3.12

echo.
echo [4/5] 创建独立的 .venv 虚拟环境...
if exist .venv (
    echo   检测到已存在 .venv，正在清理...
    rmdir /s /q .venv
)
uv venv --python 3.12
echo   .venv 虚拟环境创建完成 ✓

echo.
echo [5/5] 安装项目依赖（使用 uv sync）...
uv sync --frozen

echo.
echo ================================================
echo 安装完成！
echo.
echo 使用方法：
echo   1. 激活环境: .\.venv\Scripts\Activate.ps1
echo   2. 运行后端:   .\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8200
echo   3. 后续所有命令请使用: .\.venv\Scripts\python.exe
echo.
echo 提示：推荐将以下路径加入系统 PATH（可选）：
echo   %CD%\.venv\Scripts
echo.
echo 现在可以继续执行后续配置步骤。
pause
