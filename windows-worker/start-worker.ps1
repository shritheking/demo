# start-worker.ps1
$ErrorActionPreference = "Stop"

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -Path $scriptPath

Write-Host "Starting Infinity Trader Compilation Worker..." -ForegroundColor Cyan

# Check for .env
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found. Please copy .env.example to .env and configure it." -ForegroundColor Red
    exit 1
}

# Run the python script
python worker.py
