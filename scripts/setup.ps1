# One-time setup on Windows 10/11 (PowerShell 5.1+).   Usage:  scripts\setup.ps1 [-DownloadModels] [-SkipFrontend]
param([switch]$DownloadModels, [switch]$SkipFrontend)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-Python {
  foreach ($v in "3.12", "3.11", "3.10") { try { $p = & py "-$v" -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { return $p } } catch {} }
  throw "Python 3.10-3.12 not found. Install Python 3.12 from https://www.python.org/downloads/windows/ (tick 'Add py launcher')."
}
$Py = Find-Python
Write-Host "Using Python: $Py"
if (-not (Test-Path ".venv")) { & $Py -m venv .venv }
$VPy = Join-Path $Root ".venv\Scripts\python.exe"
& $VPy -m pip install --upgrade pip
Write-Host "Installing PyTorch (CPU build, ~200 MB)..."
& $VPy -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
& $VPy -m pip install -r backend\requirements.txt

if (-not (Test-Path ".env")) {
  $secret = & $VPy -c "import secrets;print(secrets.token_urlsafe(48))"
  (Get-Content .env.example) -replace "NYAYA_SECRET_KEY=change-me", "NYAYA_SECRET_KEY=$secret" | Set-Content .env -Encoding utf8
  Write-Host "Created .env with a generated secret key."
}

if (-not $SkipFrontend) {
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location frontend; npm ci; npm run build; Pop-Location
  } else { Write-Warning "Node.js 20+ not found: install it from https://nodejs.org to build the web UI (or run with -SkipFrontend for API only)." }
}

Push-Location backend
$env:PYTHONPATH = "$Root\backend"
& $VPy -m app.cli migrate
if ($DownloadModels) { & $VPy -m app.cli download-models }
Pop-Location
Write-Host "`nDone. Next: scripts\start.ps1   (models: scripts\setup.ps1 -DownloadModels, ~5.7 GB)" -ForegroundColor Green
