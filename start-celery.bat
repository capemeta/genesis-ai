@echo off
setlocal

echo ========================================
echo Genesis AI Celery Services Manager
echo ========================================
echo.
echo Windows Development Environment
echo Using threads pool (Windows limitation)
echo.

REM Limit BLAS/OMP threads to avoid memory pressure on Windows.
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1

REM Stop existing workers by window title first.
echo [1/4] Checking for existing Celery processes...
tasklist /FI "WINDOWTITLE eq Genesis AI - Parse Worker*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing Parse Worker, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - Parse Worker*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

tasklist /FI "WINDOWTITLE eq Genesis AI - Chunk Worker*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing Chunk Worker, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - Chunk Worker*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

tasklist /FI "WINDOWTITLE eq Genesis AI - Enhance Worker*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing Enhance Worker, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - Enhance Worker*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

tasklist /FI "WINDOWTITLE eq Genesis AI - Train Worker*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing Train Worker, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - Train Worker*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

tasklist /FI "WINDOWTITLE eq Genesis AI - WebSync Worker*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing WebSync Worker, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - WebSync Worker*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

tasklist /FI "WINDOWTITLE eq Genesis AI - Default Worker*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing Default Worker, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - Default Worker*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

tasklist /FI "WINDOWTITLE eq Genesis AI - Celery Beat*" 2>nul | find /I /N "cmd.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found existing Celery Beat, stopping...
    taskkill /FI "WINDOWTITLE eq Genesis AI - Celery Beat*" /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

REM Extra cleanup by process name.
tasklist /FI "IMAGENAME eq celery.exe" 2>nul | find /I /N "celery.exe">nul
if "%ERRORLEVEL%"=="0" (
    echo Found celery.exe processes, stopping...
    taskkill /IM celery.exe /F >nul 2>&1
    timeout /t 1 /nobreak >nul
)

echo.
echo [2/4] Switching to project directory...
cd genesis-ai-platform
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to change to genesis-ai-platform directory
    pause
    exit /b 1
)

echo [3/4] Checking virtual environment...
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\Scripts\activate.bat
    echo Please run: uv venv
    pause
    exit /b 1
)

echo.
cls
echo ========================================
echo Genesis AI Celery Services
echo ========================================
echo.
echo Windows Development Mode
echo.
echo IMPORTANT NOTES:
echo - Windows does NOT support prefork or gevent pools
echo - Using threads pool for all workers (development only)
echo - For production, deploy on Linux with proper pools
echo.
echo Starting 6 workers + Beat scheduler...
echo.

echo [4/4] Starting Celery services...
echo.

REM Parse Worker (CPU intensive)
echo [1/6] Starting Parse Worker...
echo       Queue: parse
echo       Pool: threads
echo       Concurrency: 1
start "Genesis AI - Parse Worker" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks worker -Q parse --pool=threads --concurrency=1 --loglevel=info -n parse@%%h"
timeout /t 1 /nobreak >nul

REM Chunk Worker (CPU intensive)
echo [2/6] Starting Chunk Worker...
echo       Queue: chunk
echo       Pool: threads
echo       Concurrency: 3
start "Genesis AI - Chunk Worker" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks worker -Q chunk --pool=threads --concurrency=3 --loglevel=info -n chunk@%%h"
timeout /t 1 /nobreak >nul

REM Enhance Worker (I/O intensive)
echo [3/6] Starting Enhance Worker...
echo       Queue: enhance
echo       Pool: threads
echo       Concurrency: 3
start "Genesis AI - Enhance Worker" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks worker -Q enhance --pool=threads --concurrency=3 --loglevel=info -n enhance@%%h"
timeout /t 1 /nobreak >nul

REM Train Worker (I/O intensive)
echo [4/6] Starting Train Worker...
echo       Queue: train
echo       Pool: threads
echo       Concurrency: 3
start "Genesis AI - Train Worker" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks worker -Q train --pool=threads --concurrency=3 --loglevel=info -n train@%%h"
timeout /t 1 /nobreak >nul

REM WebSync Worker (I/O intensive)
echo [5/6] Starting WebSync Worker...
echo       Queue: web_sync
echo       Pool: threads
echo       Concurrency: 4
start "Genesis AI - WebSync Worker" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks worker -Q web_sync --pool=threads --concurrency=4 --loglevel=info -n web_sync@%%h"
timeout /t 1 /nobreak >nul

REM Default Worker (maintenance tasks)
echo [6/7] Starting Default Worker...
echo       Queue: default
echo       Pool: threads
echo       Concurrency: 2
start "Genesis AI - Default Worker" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks worker -Q default --pool=threads --concurrency=2 --loglevel=info -n default@%%h"
timeout /t 1 /nobreak >nul

REM Celery Beat
echo [7/7] Starting Celery Beat...
start "Genesis AI - Celery Beat" cmd /k "cd /d %CD% && call .venv\Scripts\activate.bat && uv run celery -A tasks.celery_tasks beat --loglevel=info"

echo.
echo ========================================
echo All services started successfully.
echo ========================================
echo.
echo Service windows:
echo   [1] Parse Worker   - Queue: parse
echo   [2] Chunk Worker   - Queue: chunk
echo   [3] Enhance Worker - Queue: enhance
echo   [4] Train Worker   - Queue: train
echo   [5] WebSync Worker - Queue: web_sync
echo   [6] Default Worker - Queue: default
echo   [7] Celery Beat
echo.
echo To stop all workers, close their windows or rerun this script.
echo.

endlocal
exit /b 0
