@echo off
echo ========================================
echo   Mail Sync Tool - Starting...
echo ========================================
echo.

if not exist .venv\Scripts\activate.bat (
    echo Error: Virtual environment .venv not found.
    echo Please run setup_windows.bat first to set up the environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting Streamlit application...
echo If the browser does not open automatically, go to http://localhost:8501
echo.

streamlit run app.py --server.headless false

if %errorlevel% neq 0 (
    echo.
    echo Error: Failed to start the application.
)

pause
