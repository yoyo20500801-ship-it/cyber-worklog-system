@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   工作日誌系統 - 安裝程式
echo ============================================
echo.
echo 步驟 1：檢查 Python…
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python。
    echo 請先到 https://www.python.org/downloads/ 安裝 Python 3.10 以上，
    echo 安裝時記得勾選「Add Python to PATH」，然後再執行本檔。
    pause
    exit /b 1
)

echo 步驟 2：建立虛擬環境 venv…
python -m venv venv
if errorlevel 1 (
    echo [錯誤] 建立虛擬環境失敗。
    pause
    exit /b 1
)

echo 步驟 3：安裝相依套件（第一次約需 1-2 分鐘）…
"venv\Scripts\python.exe" -m pip install --upgrade pip >nul
"venv\Scripts\pip.exe" install -r requirements.txt
if errorlevel 1 (
    echo [錯誤] 安裝相依套件失敗，請確認網路連線後再試。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   安裝完成！
echo   之後請執行「啟動.bat」開始使用。
echo ============================================
pause
