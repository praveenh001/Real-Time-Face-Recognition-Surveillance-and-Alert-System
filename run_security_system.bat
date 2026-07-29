@echo off
title Face Recognition Security System
echo ===================================================
echo   Starting Face Recognition Security System Feed...
echo ===================================================
cd /d "%~dp0"

:: Check if virtual environment directory exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment 'venv' was not found!
    echo Please make sure you have run the installation setup first.
    pause
    exit /b 1
)

:: Activate environment and run application
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
echo [INFO] Launching Flask Dashboard...
python app.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] The application crashed or was terminated with errors.
    pause
)
