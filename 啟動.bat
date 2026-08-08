@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [錯誤] 找不到虛擬環境 venv。
    echo 請先執行「安裝.bat」建立環境，再執行本檔。
    pause
    exit /b 1
)

echo 正在啟動工作日誌系統…
"venv\Scripts\python.exe" src\main.py
pause
