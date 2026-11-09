@echo off
title PromptBeast Production Studio
color 0b

echo =======================================================
echo          PROMPTBEAST PRODUCTION STUDIO
echo =======================================================
echo.

:: Set working directory and pythonpath
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

:: Activate virtual environment if present
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
) else if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
)

:: Check if Python is installed or venv is active
python --version >nul 2>&1
if errorlevel 1 (
    color 0c
    echo [ERROR] Python is not found in your system PATH or virtual environment!
    echo Please run install.bat first to set up the application environment.
    echo.
    pause
    exit /b 1
)

echo Launching PromptBeast Desktop Studio...
echo.
python app\main.py
if errorlevel 1 (
    echo.
    echo [PromptBeast Notice] Application closed with error. Check crash.log if needed.
    echo.
    pause
)

:: Auto-close CMD window immediately upon normal application exit
exit
