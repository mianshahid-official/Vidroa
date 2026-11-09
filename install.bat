@echo off
title PromptBeast Studio - Installer
color 0b

echo =======================================================
echo          PROMPTBEAST STUDIO AUTO-INSTALLER
echo =======================================================
echo.

:: Ensure we are in the repository directory
cd /d "%~dp0"

:: 1. Detect Python
echo [1/5] Detecting Python installation...
set "PY_CMD="

python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    color 0c
    echo.
    echo =======================================================
    echo [ERROR] Python is not installed or not in system PATH!
    echo =======================================================
    echo PromptBeast requires Python 3.10+ (Python 3.10 - 3.12 recommended).
    echo.
    echo 1. Download Python from: https://www.python.org/downloads/
    echo 2. During installation, MUST CHECK: "Add python.exe to PATH"
    echo 3. After installing, run install.bat again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PY_CMD% --version') do echo Found: %%i

:: 2. Setup Virtual Environment
echo.
echo [2/5] Setting up Python virtual environment (venv)...
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment in .\venv...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo [WARNING] Could not create virtual environment.
        echo Will attempt installation directly with %PY_CMD%...
    )
) else (
    echo Existing virtual environment found in .\venv.
)

if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "venv\Scripts\activate.bat"
)

:: 3. Setup Environment Variables (.env)
echo.
echo [3/5] Checking configuration (.env)...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo Created .env from .env.example
    ) else (
        type nul > ".env"
        echo Created empty .env file
    )
) else (
    echo .env file already exists.
)

:: 4. Upgrade pip and install dependencies
echo.
echo [4/5] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [5/5] Installing dependencies from requirements.txt...
echo This may take a few minutes on a new machine, please wait...
python -m pip install -r requirements.txt
if errorlevel 1 (
    color 0c
    echo.
    echo =======================================================
    echo [ERROR] Failed to install all dependencies!
    echo =======================================================
    echo Please check your internet connection or Python version.
    echo You can re-run install.bat at any time.
    echo.
    pause
    exit /b 1
)

:: Quick verification
echo.
echo Verifying core installation...
python -c "import PySide6, pydantic, groq, PIL; print('[OK] Core dependencies verified successfully!')"
if errorlevel 1 (
    echo [WARNING] Core verification reported a problem. Check errors above.
)

color 0a
echo.
echo =======================================================
echo          INSTALLATION COMPLETED SUCCESSFULLY!
echo =======================================================
echo.
echo All required packages and configurations are installed.
echo You can now launch PromptBeast anytime by double-clicking:
echo.
echo       run.bat
echo.
echo =======================================================
echo.
pause
