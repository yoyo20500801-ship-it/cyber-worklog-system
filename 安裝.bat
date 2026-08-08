@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Worklog System - Installer
echo ============================================
echo.
echo Step 1: Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ from:
    echo   https://www.python.org/downloads/
    echo and check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Step 2: Creating virtual environment venv...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create the virtual environment.
    pause
    exit /b 1
)

echo Step 3: Installing dependencies (about 1-2 min on first run)...
"venv\Scripts\python.exe" -m pip install --upgrade pip >nul
"venv\Scripts\pip.exe" install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Please check your network and retry.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation complete!
echo   Run the start batch file to launch the app.
echo ============================================
pause
