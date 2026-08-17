$action = New-ScheduledTaskAction -Execute "C:\mt5-license-system\windows-worker\start_worker.bat" -WorkingDirectory "C:\mt5-license-system\windows-worker"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "MT5WorkerService" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
Write-Host "Scheduled Task 'MT5WorkerService' registered successfully."
