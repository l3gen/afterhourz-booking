# One-time setup for local development on Windows.
# Run from the project root:  .\win-setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "`n== Checking prerequisites ==" -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Python not found. Install Python 3.11+ from python.org and tick 'Add to PATH'." }
$pyver = (python --version)
Write-Host "  $pyver"

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw "Node not found. Install Node 20+ from nodejs.org." }
Write-Host "  node $(node --version)"

Write-Host "`n== Creating Python virtual environment (.venv) ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { python -m venv .venv }

Write-Host "`n== Installing backend dependencies (this takes a few minutes) ==" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r backend\requirements-dev.txt

Write-Host "`n== Installing frontend dependencies ==" -ForegroundColor Cyan
Push-Location frontend
npm install
Pop-Location

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Now open three PowerShell windows in this folder and run, one per window:"
Write-Host "  1)  .\win-db.ps1"
Write-Host "  2)  .\win-api.ps1"
Write-Host "  3)  .\win-web.ps1"
Write-Host "Then open http://localhost:5173"
