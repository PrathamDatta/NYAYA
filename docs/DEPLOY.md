# Running and deploying

## A. Windows 11 laptop (recommended path, no Docker, no database server)

Requirements: Python 3.11 or 3.12 (3.12 recommended, install from python.org with the *py launcher*), Node.js 20+ (only to build the UI once), ~8 GB free disk (6 GB models), 8 GB RAM minimum (16 GB comfortable).

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
* **8 GB RAM**: set `NYAYA_MEMORY_BUDGET_MB=4800` in `.env`; the translator (≈4.2 GB resident) and the BERTs (≈0.7 GB each) then swap in and out (first use after a swap costs a model load of several seconds). `NYAYA_TRANSLATION_QUANTIZE_INT8=true` makes translation ≈2.5× faster but, as measured, does **not** reduce memory (5.4 GB vs 4.2 GB resident), and its translation quality has not been evaluated. On 8 GB machines the OS and browser also need memory: if swapping is heavy, skip translation.
* Keep the repo path short (Windows 260-char path limit applies to the Hugging Face cache).
* Windows may print a symlink warning from huggingface_hub; the scripts set `HF_HUB_DISABLE_SYMLINKS_WARNING=1`. Without Developer Mode, files are copied instead of linked (slightly more disk).
* Use BitLocker for data-at-rest encryption of uploaded documents.
* First request after start-up is slow (models load lazily).

> **Verification status:** `scripts/setup.sh` (the Linux equivalent) was run from a fresh `git clone` on Linux/Python 3.12: it installed the pinned dependencies and CPU PyTorch, applied migrations, and the 49 backend tests passed (model download and UI build were skipped in that run). The Windows scripts (`.ps1`/`.bat`) follow the same steps but have **not been run on Windows 11**. The Python code is OS-neutral (pathlib; the only POSIX-only call, `resource`, is in the evaluation script). Please report any first-run problem.

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
