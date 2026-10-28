# Run any maintenance command, e.g.:  scripts\cli.ps1 download-models   |   scripts\cli.ps1 ingest-sci --year 2023 --limit 40
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
& "$Root\.venv\Scripts\python.exe" -m app.cli @args
