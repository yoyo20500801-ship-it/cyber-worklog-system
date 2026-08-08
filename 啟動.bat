@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run the install batch file once, then retry.
    pause
    exit /b 1
)

echo Starting Worklog System...
"venv\Scripts\python.exe" src\main.py
pause
