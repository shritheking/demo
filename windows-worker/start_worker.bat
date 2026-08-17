@echo off
cd /d C:\mt5-license-system\windows-worker
echo [%date% %time%] Starting MT5 Worker... >> worker_service.log
C:\Users\infinityadmin\AppData\Local\Programs\Python\Python313\python.exe worker.py >> worker_service.log 2>&1
