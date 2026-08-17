# install.ps1
# Registers a Windows Scheduled Task to run the worker automatically on startup

$ErrorActionPreference = "Stop"

# Require Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Please run this script as Administrator."
    exit 1
}

$taskName = "InfinityTraderWorker"
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$workerScript = Join-Path $scriptPath "start-worker.ps1"

Write-Host "Registering Scheduled Task: $taskName" -ForegroundColor Cyan
Write-Host "Worker directory: $scriptPath"

# Action: run PowerShell silently to execute our wrapper script
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$workerScript`"" -WorkingDirectory $scriptPath

# Trigger: at startup
$trigger = New-ScheduledTaskTrigger -AtStartup

# Settings: run regardless of network, allow start if on batteries, don't stop on idle end
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd

# Principal: Run as SYSTEM so it runs unattended without a logged-in user session
# Note: If MetaEditor fails because it needs a real user profile, change UserId to the actual VPS administrator account
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register
Register-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -TaskName $taskName -Force

Write-Host "Task '$taskName' registered successfully." -ForegroundColor Green
Write-Host "You can manage this task in 'Task Scheduler' (taskschd.msc)."
Write-Host "To start it immediately, run:"
Write-Host "Start-ScheduledTask -TaskName $taskName"
