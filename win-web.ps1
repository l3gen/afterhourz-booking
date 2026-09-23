# Terminal 3: the React site on port 5173, proxying /api to the backend on 8000.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Starting the site on http://localhost:5173" -ForegroundColor Cyan
Write-Host "Ctrl+C to stop.`n"
Set-Location frontend
npm run dev
