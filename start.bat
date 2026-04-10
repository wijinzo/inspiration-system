@echo off
cd /d "%~dp0"
echo ==============================================================
echo       🧪 Science Script Engine (V3) - 啟動器
echo ==============================================================
echo.

:: 1. 檢查 .env 是否存在
if not exist .env (
    echo [WARNING] 找不到 .env 設定檔！
    if exist .env.example (
        echo [INFO] 正在從 .env.example 複製範本...
        copy .env.example .env
        echo [!] 請記得在 .env 中填入您的 API Key。
    ) else (
        echo [ERROR] 找不到 .env.example，請手動建立 .env 檔案。
        pause
        exit /b
    )
    echo.
)

:: 2. 環境檢查與自動安裝
if not exist venv\Scripts\activate.bat (
    echo [INFO] 找不到虛擬環境，正在進行首次安裝...
    echo [INFO] 正在建立 venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Python 未安裝或未加入環境變數，請先安裝 Python。
        pause
        exit /b
    )
    echo [INFO] 正在安裝依賴套件 (requirements.txt)...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo [SUCCESS] 環境安裝完成。
    echo.
) else (
    echo [INFO] 偵測到虛擬環境，正在啟動...
    call venv\Scripts\activate.bat
)

:: 3. 檢查資料庫是否存在，若無則執行首次爬取
if not exist articles.db (
    echo [INFO] 偵測到資料庫不完整，正在執行首次資料爬取 (populate_db.py)...
    python populate_db.py
    echo [SUCCESS] 首次爬取完成。
    echo.
)

:: 4. 啟動後端
echo [INFO] 正在啟動後端服務 (FastAPI)...
start "Science Engine Backend" cmd /k "python app.py"

:: 5. 等待啟動並開啟瀏覽器
echo [INFO] 等待服務初始化中...
timeout /t 3 /nobreak >nul

set APP_URL=http://127.0.0.1:8000
echo [INFO] 正在開啟瀏覽器: %APP_URL%
start %APP_URL%

echo.
echo ==============================================================
echo 🚀 引擎已啟動！
echo 若有報錯，請檢查另一個黑色終端機視窗。
echo 按任意鍵關閉此啟動引導視窗...
echo ==============================================================
pause >nul
