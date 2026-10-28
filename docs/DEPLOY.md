# Running and deploying

## A. Windows 11 laptop (recommended path, no Docker, no database server)

Requirements: Python 3.10–3.12 (3.12 recommended, install from python.org with the *py launcher*), Node.js 20+ (only to build the UI once), ~8 GB free disk (6 GB models), 8 GB RAM minimum (16 GB comfortable).

```bat
git clone https://github.com/PrathamDatta/NYAYA && cd NYAYA
scripts\setup.bat -DownloadModels
scripts\start.bat
```
Open http://127.0.0.1:8000. `setup` creates `.venv`, installs the CPU build of PyTorch and pinned dependencies, writes `.env` with a generated secret, builds the UI, applies migrations and (with `-DownloadModels`) downloads the four pinned models (~5.7 GB, once).

Load legal sources (see `docs/INGESTION.md`):
```bat
scripts\cli.bat ingest-sci --year 2023 --limit 40
scripts\cli.bat ingest-manifest corpus\manifest.json
```
Tips for laptops
* **8 GB RAM**: set `NYAYA_MEMORY_BUDGET_MB=4500` in `.env`; the translator (≈4.3 GB peak) and the BERTs then swap in and out (first use after a swap costs a model load). `NYAYA_TRANSLATION_QUANTIZE_INT8=true` reduces translator memory — measured effect in `docs/EVALUATION.md`.
* Keep the repo path short (Windows 260-char path limit applies to the Hugging Face cache).
* Windows may print a symlink warning from huggingface_hub; the scripts set `HF_HUB_DISABLE_SYMLINKS_WARNING=1`. Without Developer Mode, files are copied instead of linked (slightly more disk).
* Use BitLocker for data-at-rest encryption of uploaded documents.
* First request after start-up is slow (models load lazily).

> **Verification status:** the setup scripts for Windows (`.ps1`/`.bat`) were written to mirror the Linux flow that *was* executed in CI-like conditions, but they have **not been run on Windows 11** in this build. The Python code paths are OS-neutral (pathlib, no POSIX-only calls except `resource` in the evaluation script). Please report any first-run problem.

## B. Linux/macOS
`scripts/setup.sh --download-models && scripts/start.sh`.

## C. Development
```bash
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload     # API on :8000
cd frontend && npm run dev                                              # UI on :5173 (proxies /api to :8000)
```

## D. Split hosting (frontend on Vercel, API elsewhere)
* Frontend: set the Vercel project root to `frontend/`, build `npm run build`, output `dist`, env `VITE_API_BASE=https://api.example.com`, and add an SPA rewrite (`/(.*)` → `/index.html`).
* Backend: any host with ≥ 8 GB RAM and ~8 GB disk (CPU is sufficient; GPU optional via `NYAYA_DEVICE=cuda` — untested). **Vercel cannot host the model workload** (serverless memory/time limits and 6 GB of weights).
* Cookies are cross-site in this topology: serve both under one registrable domain (e.g. `app.example.com` and `api.example.com`) and set `NYAYA_COOKIE_SECURE=true`, `NYAYA_CORS_ORIGINS=["https://app.example.com"]`. SameSite=Lax cookies will **not** be sent for requests between unrelated domains.
* **No live deployment was created or verified in this build.** The Vercel URL above is the *previous* product.

## Production checklist
`NYAYA_ENV=production` (refuses to start with the default secret; hides `/api/docs`), `NYAYA_SECRET_KEY` long random, HTTPS, `NYAYA_COOKIE_SECURE=true`, back up `data/nyaya.db` and `data/uploads/`, restrict disk access.

## Health
`GET /api/health` (liveness), `GET /api/ready` (DB reachable + corpus size), `GET /api/system/status` (models, corpus, limits).

## Database provisioning and migrations
SQLite is created automatically. Apply migrations explicitly with `python -m app.cli migrate` (the app also runs them at start). For PostgreSQL: create an empty database, set `NYAYA_DATABASE_URL`, install `psycopg[binary]`, run migrate.

## Rollback
* Code: `git checkout <previous tag/commit>` then restart. Migrations are additive; to roll the schema back run `alembic downgrade -1` from `backend/` (data in dropped tables is lost — back up first).
* Models: revisions are pinned; to roll back a model change, restore the old revision in `registry.py`, re-download, and re-embed.
* Data: restore `data/nyaya.db` and `data/uploads/` from backup.
