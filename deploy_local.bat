@echo off
REM AI Employee Zoya - Local Deployment Script
REM Starts the complete environment with one click

echo =====================================================
echo AI Employee Zoya - Local-First Deployment
echo Starting complete environment...
echo =====================================================

REM Create necessary directories if they don't exist
if not exist "logs" mkdir logs
if not exist "obsidian_vault\inbox" mkdir obsidian_vault\inbox
if not exist "obsidian_vault\needs_action" mkdir obsidian_vault\needs_action
if not exist "obsidian_vault\Plans" mkdir obsidian_vault\Plans
if not exist "obsidian_vault\Approved" mkdir obsidian_vault\Approved
if not exist "obsidian_vault\Done" mkdir obsidian_vault\Done

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher and add it to your PATH
    pause
    exit /b 1
)

REM Check if required packages are installed
echo Checking required packages...
python -c "import watchdog" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install watchdog psutil
)

REM Start the AI Employee Zoya in background mode
echo Starting AI Employee Zoya in background mode...
start "AI Employee Zoya" /min python start_agent.py

REM Wait a moment to ensure the process started
timeout /t 3 /nobreak >nul

REM Check if the process is running
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "start_agent.py">NUL
if "%ERRORLEVEL%"=="0" (
    echo.
    echo SUCCESS: AI Employee Zoya is running in the background!
    echo.
    echo The system is now monitoring:
    echo - Inbox folder for new tasks
    echo - Processing tasks through the workflow
    echo - Executing approved plans
    echo - Performing health checks every 5 minutes
    echo.
    echo To view logs, check the 'logs' folder
    echo To stop the agent, run: taskkill /f /im python.exe
    echo.
) else (
    echo.
    echo WARNING: Could not confirm AI Employee Zoya is running
    echo Check the logs folder for error details
    echo.
)

echo Press any key to exit...
pause >nul