@echo off
echo ========================================
echo   Mail Sync Tool - Setup Script
echo ========================================
echo.

echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found! Please install Python 3.11 or higher.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo   Python is available.

echo [2/4] Creating virtual environment (.venv)...
if exist .venv (
    echo   Virtual environment already exists, skipping creation.
) else (
    python -m venv .venv
    echo   Virtual environment created successfully.
)

echo [3/4] Activating virtual environment...
call .venv\Scripts\activate.bat
echo   Virtual environment activated.

echo [4/4] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo   Error: Failed to install dependencies. Please check your internet connection.
    pause
    exit /b 1
)
echo   Dependencies installed successfully.

echo.
echo ========================================
echo   Setup completed successfully!
echo ========================================
echo.
echo To start the application, double-click run_windows.bat
echo.
pause
