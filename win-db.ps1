# Terminal 1: local DynamoDB stand-in (moto) on port 8001.
# Leave this window running. Data resets when you stop it.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:AWS_ACCESS_KEY_ID = "local"
$env:AWS_SECRET_ACCESS_KEY = "local"
$env:AWS_DEFAULT_REGION = "us-east-1"

Write-Host "Starting local DynamoDB (moto) on http://localhost:8001 ..." -ForegroundColor Cyan
Write-Host "Leave this window open. Ctrl+C to stop.`n"
& .\.venv\Scripts\moto_server.exe -p 8001
