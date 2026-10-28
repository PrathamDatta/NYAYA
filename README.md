# Nyaya Bharatha

Indian legal **information** and drafting assistance: ask a question and get passages from ingested legal sources with
verifiable citations, search the library, analyse your documents, prepare editable drafts, translate into nine Indian
languages, and find free legal aid. Runs entirely on local open models — **no external AI API** — and is designed to be
hosted on an ordinary Windows 11 laptop.

> Legal information, not legal advice. See `docs/AUDIT.md` for what the original product was and `docs/EVALUATION.md` for what is measured.

## Quick start (Windows 11)

```bat
scripts\setup.bat -DownloadModels   :: installs Python deps, builds the UI, downloads ~5.7 GB of pinned models
scripts\start.bat                   :: http://127.0.0.1:8000
scripts\cli.bat ingest-sci --year 2023 --limit 40
```
Easiest on Windows: double-click `RUN-NYAYA.bat` (installs what is missing, downloads models, loads sample judgments, starts the app, opens the browser).

Linux/macOS: `scripts/setup.sh --download-models && scripts/start.sh`. Details, 8 GB-RAM tuning, split hosting (Vercel) and rollback: `docs/DEPLOY.md`.

## What is inside

| Path | Contents |
|---|---|
| `backend/app` | FastAPI app: `routers/`, `rag/` (chunking, BM25, hybrid retriever, generator, citation validator, pipeline, ingestion), `ml/` (model registry, encoders, translation), `docs/` (extraction, analysis, drafting) |
| `backend/alembic` | database migrations |
| `backend/tests`, `backend/eval` | pytest suite; repeatable model/RAG evaluation |
| `frontend` | React + TypeScript + Tailwind UI (Vite) |
| `e2e/journeys.mjs` | Playwright end-to-end journeys (desktop + mobile) |
| `docs/` | AUDIT, ARCHITECTURE, MODELS, INGESTION, EVALUATION, SECURITY, DEPLOY |

## The four required models

`law-ai/InLegalBERT`, `law-ai/InCaseLawBERT`, `law-ai/CustomInLawBERT` and `law-ai/InLegalTrans-En2Indic-1B`, pinned to exact
revisions, each integrated for the task its architecture supports — see `docs/MODELS.md`. They retrieve and translate; they do not write answers.

## Commands

```bash
cd backend
python -m pytest                       # backend tests
ruff check . && mypy app               # lint + types
python -m eval.run_eval all            # measure retrieval / topic / gate / pipeline / translation / resources
python -m eval.report                  # regenerate docs/EVALUATION.md
cd ../frontend && npm run lint && npm run typecheck && npm test && npm run build
# end-to-end: start the server with a raised auth limit (each run registers ~4 accounts; the default is 10 auth requests/min/IP)
NYAYA_AUTH_RATE_LIMIT_PER_MINUTE=1000 scripts/start.sh &
BASE_URL=http://127.0.0.1:8000 node ../e2e/journeys.mjs   # needs Playwright (npm i -g playwright)
```

## Honest status

`docs/STATUS.md` classifies every deliverable (verified / not fully verified / not implemented) and lists known limitations.
