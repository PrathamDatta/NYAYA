#!/usr/bin/env bash
# Linux/macOS equivalent of setup.ps1.   Usage: scripts/setup.sh [--download-models] [--skip-frontend]
set -euo pipefail
cd "$(dirname "$0")/.."
PY=$(command -v python3.12 || command -v python3.11 || true); [ -n "$PY" ] || { echo "Need Python 3.11 or 3.12"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r backend/requirements.txt
if [ ! -f .env ]; then sed "s|NYAYA_SECRET_KEY=change-me|NYAYA_SECRET_KEY=$(.venv/bin/python -c 'import secrets;print(secrets.token_urlsafe(48))')|" .env.example > .env; fi
if [[ ! " $* " =~ " --skip-frontend " ]] && command -v npm >/dev/null; then (cd frontend && npm ci && npm run build); fi
(cd backend && ../.venv/bin/python -m app.cli migrate)
[[ " $* " =~ " --download-models " ]] && (cd backend && ../.venv/bin/python -m app.cli download-models)
echo "Done. Start with: scripts/start.sh"
