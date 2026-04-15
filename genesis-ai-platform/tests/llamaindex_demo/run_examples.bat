@echo off
REM LlamaIndex Examples Runner
echo ========================================
echo LlamaIndex Examples Runner
echo ========================================
echo.

REM Set the Python executable from uv virtual environment
set PYTHON_EXE=..\..\.venv\Scripts\python.exe

REM Check if virtual environment exists
if not exist "%PYTHON_EXE%" (
    echo Error: Virtual environment not found!
    echo Please run 'uv sync' in the genesis-ai-platform directory first.
    pause
    exit /b 1
)

echo Select an example to run:
echo 1. RAG Chat Engine Demo
echo 2. Simple Chat Demo
echo 3. Function Agent Demo
echo 4. Exit
echo.

set /p choice=Enter your choice (1-4): 

if "%choice%"=="1" (
    echo.
    echo Running RAG Chat Engine Demo...
    "%PYTHON_EXE%" examples\01_chat_engine_demo.py
) else if "%choice%"=="2" (
    echo.
    echo Running Simple Chat Demo...
    "%PYTHON_EXE%" examples\02_simple_chat_demo.py
) else if "%choice%"=="3" (
    echo.
    echo Running Function Agent Demo...
    "%PYTHON_EXE%" examples\03_function_agent_demo.py
) else if "%choice%"=="4" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid option, please run the script again
)

echo.
pause
