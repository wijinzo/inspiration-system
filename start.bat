@echo off
cd /d "%~dp0"
echo ==============================================================
echo       Starting Science Script Engine (V3)
echo ==============================================================
echo.

if not exist venv\Scripts\activate.bat goto novenv
echo [INFO] Virtual environment found. Activating...
call venv\Scripts\activate.bat
goto startapp

:novenv
echo [INFO] No virtual environment found. Using global Python.

:startapp
echo [INFO] Starting Backend Server (FastAPI)...
start "Science Engine Backend" cmd /k "python app.py"

echo [INFO] Waiting for server to initialize (3 seconds)...
timeout /t 3 /nobreak >nul

echo [INFO] Opening Browser...
start http://127.0.0.1:8000

echo.
echo ==============================================================
echo If an error occurs, please check the other black terminal window.
echo Press any key to close this launcher...
echo ==============================================================
pause >nul
