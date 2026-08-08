@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run the install batch file once, then retry.
    pause
    exit /b 1
)

start "" "venv\Scripts\pythonw.exe" src\main.py
exit
