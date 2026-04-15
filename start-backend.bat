@echo off
echo ========================================
echo Starting Genesis AI Backend Server
echo ========================================
echo.

REM 先结束占用 8200 端口的进程，避免控制台退出后后台仍在
echo Checking for existing process on port 8200...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8200" ^| findstr "LISTENING"') do (
    echo Stopping existing process PID %%a...
    taskkill /PID %%a /F >nul 2>&1
    timeout /t 1 /nobreak >nul
    goto :backend_done_kill
)
:backend_done_kill
echo.

cd genesis-ai-platform

echo Activating virtual environment...
call .venv\Scripts\activate.bat

cls
echo ========================================
echo Genesis AI Backend Server
echo ========================================
echo.
echo IMPORTANT: Celery workers should be started separately!
echo Run start-celery.bat in another terminal to start Celery services.
echo.
echo Starting FastAPI server...
echo Server URL: http://localhost:8200
echo API Docs: http://localhost:8200/docs
echo.
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8200
