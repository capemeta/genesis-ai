@echo off
echo ========================================
echo Genesis AI Task Monitor (Flower)
echo ========================================
echo.

REM 1. 切换到项目目录
echo [1/3] Switching to project directory...
cd genesis-ai-platform
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to change to genesis-ai-platform directory
    pause
    exit /b 1
)

REM 2. 检查虚拟环境
echo [2/3] Checking virtual environment...
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\Scripts\activate.bat
    echo Please run: uv venv
    pause
    exit /b 1
)

REM 3. 检查 Flower 是否已安装
echo [3/3] Checking Flower installation...
call .venv\Scripts\activate.bat
python -c "import flower" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Flower not found, installing...
    uv pip install flower
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to install Flower
        pause
        exit /b 1
    )
)

echo.
cls
echo ========================================
echo Genesis AI Task Monitor (Flower)
echo ========================================
echo.
echo Starting Flower web interface...
echo.
echo Access URL: http://localhost:5555
echo.
echo Press Ctrl+C to stop the monitor
echo.
echo ========================================
echo.

REM 启动 Flower
uv run celery -A tasks.celery_tasks flower --port=5555

pause
