# Architecture

```
Browser (React SPA)  ──HTTPS/JSON──▶  FastAPI app (single process, laptop-friendly)
                                         ├─ routers: auth · chat(ask/translate) · library · documents · drafts · cases · aid · system
                                         ├─ SQLAlchemy ─▶ SQLite (default) | PostgreSQL        (Alembic migrations)
                                         ├─ rag/   chunking · BM25 · dense index (numpy) · retriever · generator · citations · pipeline · ingest
                                         ├─ ml/    registry (pinned revisions, LRU by RAM) · encoders (3×BERT) · translation (InLegalTrans)
                                         ├─ docs/  extraction (PDF/DOCX/TXT/OCR) · analysis · drafting
                                         └─ data/  uploads/  models/ (HF cache)  nyaya.db
```

## Key decisions

| Decision | Rationale |
|---|---|
| **Keep Vite/React/TS/Tailwind** instead of migrating to Next.js | It is what the deployed product uses; the app needs no SSR; a static bundle deploys to Vercel and is also served by FastAPI for laptop hosting. |
| **FastAPI + SQLAlchemy + Alembic** | Same Python runtime as the ML stack: no extra service boundary. Modules are separated by responsibility (HTTP, retrieval, models, documents) but run in one process, avoiding unnecessary microservices. |
| **SQLite by default, PostgreSQL optional** | A Windows laptop should not need Docker or a DB server. SQLAlchemy models are portable; set `NYAYA_DATABASE_URL=postgresql+psycopg://…` and install `psycopg` to use PostgreSQL. **The PostgreSQL path is untested in this build.** |
| **Exact numpy search instead of pgvector** | Vectors live in the DB as float32 blobs and are loaded into an in-memory matrix per encoder. At laptop scale (≤ ~10⁵ passages × 768 dims ≈ 300 MB) this is exact and fast. For larger corpora replace `CorpusIndex` with pgvector (`vector(768)` + HNSW) — the schema already stores per-model, per-revision vectors. This was a measured-need decision, not a pgvector rejection. |
| **Hybrid BM25 + dense with reciprocal-rank fusion** | MLM encoders are weak raw embedders; lexical matching anchors precision. Which dense components are enabled by default is set from measured results (docs/EVALUATION.md). |
| **Extractive answers by default** | A free-text generator can hallucinate legal claims. Quoting retrieved passages is verifiable. A local LLM is available as an opt-in. |
| **Evidence gate** | The answer is refused unless retrieved passages jointly cover an IDF-weighted share (≥ `NYAYA_MIN_QUERY_COVERAGE`) of the question's terms; terms unknown to the corpus count against coverage. |
| **Cookie sessions, not JWT** | Server-side revocation, HttpOnly cookies, no token in JS. |

## Pipeline (`LegalResponsePipeline`)

1. Normalise the question; light lay→legal expansion (lexical only).
2. Topic: `CustomLegalNLP.classify_topic` (CustomInLawBERT prototype similarity) cross-checked with keywords.
3. `LegalRetriever.search`: filters (type, year, jurisdiction, **as-of date**, historical flag) → BM25 + InLegalBERT + InCaseLawBERT rankings → RRF.
4. Temporal validation from stored status/effective dates only; unverified status is surfaced as a warning.
5. Evidence gate (coverage) → decline with an explicit message, or continue.
6. `LegalAnswerGenerator` (extractive | local_llm).
7. `CitationValidator`: markers, quotation segments, URLs, statutory references.
8. Structured response: answer, citations with pinpoints and provenance, uncertainties, clarifying questions, next steps, urgent contacts, disclaimer, models used, timings.

## Database

Tables: `users, auth_sessions, cases, conversations, messages, legal_sources, legal_chunks, chunk_embeddings, uploaded_documents, drafts, draft_revisions, audit_events` (migration `0001_initial_schema`). Foreign keys cascade on user deletion; case deletion detaches children (`SET NULL`). Unique `(identifier, version, doc_type)` on sources; unique `(chunk_id, model_key)` on embeddings. Processing jobs are represented by `uploaded_documents.status` (queued → processing → done | failed) run through FastAPI background tasks; there is no separate job queue (single-process design).

## API summary (OpenAPI at `/api/docs` in development)

`POST /api/auth/{register,login,logout}` · `GET /api/auth/{me,export}` · `DELETE /api/auth/account` · `POST /api/ask` · `POST /api/translate` · `GET|DELETE /api/conversations[/id]` · `GET /api/library/{search,sources,sources/id}` · `POST|GET|DELETE /api/documents[/id]` · `GET /api/documents/inconsistencies` · `POST /api/documents/id/retry` · `GET|POST|PUT|DELETE /api/drafts[/id]` · `GET /api/drafts/id/export?format=docx|txt` · `CRUD /api/cases` · `GET /api/aid/directory` · `GET /api/{health,ready,system/status}`.
Errors use one envelope: `{"error": {"code", "message", ...}}` with `unauthorized, forbidden, not_found, validation_error, csrf, rate_limited, too_large, model_unavailable (503), internal_error`.
