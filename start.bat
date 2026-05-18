@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================================
echo       Science Script Engine (V3) - Starter
echo ==============================================================
echo.

REM 1. Check .env
if not exist .env (
    echo [WARNING] .env file not found!
    if exist .env.example (
        echo [INFO] Copying template from .env.example...
        copy .env.example .env
        echo [!] Please fill in your API Keys in the .env file.
    ) else (
        echo [ERROR] .env.example not found.
        pause
        exit /b
    )
    echo.
)

REM 2. Environment check
if not exist venv\Scripts\activate.bat (
    echo [INFO] Virtual environment not found. Setting up...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Python not found. Please install Python.
        pause
        exit /b
    )
    echo [INFO] Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo [SUCCESS] Setup complete.
    echo.
) else (
    echo [INFO] Activating environment...
    call venv\Scripts\activate.bat
    echo [INFO] Checking for missing packages...
    pip install -r requirements.txt --quiet
    echo [INFO] Dependencies up to date.
    echo.
)

REM 3. Database check
if not exist articles.db (
    echo [INFO] Database not found. Initializing...
    python populate_db.py
)

REM 4. Start Backend
echo [INFO] Starting Backend...
start "Science Engine Backend" cmd /k "python app.py"

REM 5. Open Browser
echo [INFO] Opening browser...
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8000

echo.
echo ==============================================================
echo System Started.
echo Press any key to exit this window.
echo ==============================================================
pause >nul
