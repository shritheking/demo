@echo off
title MT5 License System Services Starter

echo Starting Infinity Trader System...

:: 1. Start Backend API
echo Starting Backend API...
start "Backend API" cmd /c "cd /d C:\mt5-license-system\backend && py -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: 2. Start Telegram Bot
echo Starting Telegram Bot...
start "Telegram Bot" cmd /c "cd /d C:\mt5-license-system\telegram_bot && py bot.py"

:: 3. Start Windows Worker
echo Starting Compiler Worker...
start "Compiler Worker" cmd /c "cd /d C:\mt5-license-system\windows-worker && py worker.py"

echo All services have been launched in separate windows!
echo To run this automatically on startup, configure this script in Windows Task Scheduler.
pause
