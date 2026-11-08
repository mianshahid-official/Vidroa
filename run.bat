@echo off
title PromptBeast Production Studio
color 0b

echo =======================================================
echo          PROMPTBEAST PRODUCTION STUDIO
echo =======================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    color 0c
    echo [ERROR] Python is not found in your system PATH!
    echo Please install Python 3.10+ and check 'Add python.exe to PATH'.
    echo.
    pause
    exit
)

:: Set working directory and pythonpath
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

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
