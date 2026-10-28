# Starts the API and web UI on http://127.0.0.1:8000   Usage: scripts\start.ps1 [-Port 8000]
param([int]$Port = 8000)
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
Write-Host "Nyaya Bharatha -> http://127.0.0.1:$Port  (Ctrl+C to stop)"
& "$Root\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port $Port
