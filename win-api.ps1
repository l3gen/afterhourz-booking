# Terminal 2: the FastAPI backend on port 8000.
# Creates the table first (safe to re-run), then serves with auto-reload.
# Start win-db.ps1 before this one.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:AWS_ACCESS_KEY_ID = "local"
$env:AWS_SECRET_ACCESS_KEY = "local"
$env:AWS_DEFAULT_REGION = "us-east-1"
$env:AWS_REGION = "us-east-1"
$env:DYNAMODB_ENDPOINT_URL = "http://localhost:8001"
$env:TABLE_NAME = "afterhourz-local"
$env:ENV = "local"
$env:DEV_LOGIN_ENABLED = "true"
if (-not $env:ADMIN_EMAILS) { $env:ADMIN_EMAILS = "owner@example.com" }

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvUvicorn = Join-Path $PSScriptRoot ".venv\Scripts\uvicorn.exe"

Push-Location backend
Write-Host "Creating the DynamoDB table if it does not exist ..." -ForegroundColor Cyan
& $venvPython scripts\create_table.py

Write-Host "`nStarting the API on http://localhost:8000" -ForegroundColor Cyan
Write-Host "Admin sign-in email: $env:ADMIN_EMAILS"
Write-Host "API docs: http://localhost:8000/docs`n"
& $venvUvicorn app.main:app --reload --port 8000
Pop-Location
