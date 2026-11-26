@echo off
title Vidroa Production Studio
color 0b

echo =======================================================
echo             VIDROA PRODUCTION STUDIO
echo =======================================================
echo.

cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

set "PYTHON_EXE=python"
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    color 0c
    echo [ERROR] Python is not found in your system PATH!
    echo Please install Python 3.10+ and check 'Add python.exe to PATH'.
    echo.
    pause
    exit /b 1
)

%PYTHON_EXE% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    color 0c
    echo [ERROR] Python 3.10+ is required. Detected older version:
    %PYTHON_EXE% --version
    echo.
    pause
    exit /b 1
)

echo Launching Vidroa Desktop Studio using %PYTHON_EXE%...
echo.
%PYTHON_EXE% app\main.py
if errorlevel 1 (
    echo.
    echo [Vidroa Notice] Application closed with error. Check crash.log if needed.
    echo.
    pause
)

exit
