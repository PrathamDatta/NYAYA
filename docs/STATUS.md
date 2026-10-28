# Status of deliverables, test results and known limitations

Classification: **V** = implemented and verified (by tests or a real run described below) · **P** = implemented, not fully verified · **N** = not implemented.

## Deliverables

| # | Deliverable | Status | Evidence / note |
|---|---|---|---|
| 1 | Original application audit | **V** | `docs/AUDIT.md`. The repository was empty (single "Remove project" commit); the live site was audited from its served bundle. |
| 2 | Architecture and technology choices | **V** | `docs/ARCHITECTURE.md` |
| 3 | Redesigned UI (landing, auth, ask, library, documents, drafts, cases, translate, aid, settings, status, policies) | **V** | 13/13 Playwright journeys (desktop + 390 px mobile), 14 Vitest tests, eslint/tsc clean, production build. Dark mode and reduced-motion implemented; a formal accessibility audit (axe/screen-reader) was **not** run. |
| 4 | Backend: auth, isolation, validation, rate limits, errors | **V** | 65 pytest tests incl. cross-user isolation, CSRF, malicious uploads, rate limiting, account deletion |
| 5 | Database schema + migrations | **V** (SQLite) / **P** (PostgreSQL) | Migration `0001` applied from scratch in tests and in a clean clone. PostgreSQL never run. |
| 6 | Four Law-AI models integrated at pinned revisions | **V** | Real weights loaded and run; roles chosen by measurement (`docs/MODELS.md`, `docs/EVALUATION.md`) |
| 7 | Translation, 9 languages | **V** for functioning, script and latency; **P** for quality | All nine languages produce target-script output on real weights. No reference translations offline, so BLEU/chrF were **not** measured here. |
| 8 | Legal corpus + RAG + citation validation | **V** pipeline / **P** content | 60 real Supreme Court judgments (2023) ingested and searchable; **no statutes ingested** (see limitations) |
| 9 | Document upload, extraction, analysis | **V** for TXT/PDF/DOCX; **P** for OCR | OCR needs the optional `rapidocr-onnxruntime`; only the "not installed" error path is tested |
| 10 | Drafting + export | **V** | 4 templates; DOCX and TXT export verified; PDF export deliberately not offered |
| 11 | Evaluation suite | **V** | `python -m eval.run_eval all`; results in `docs/EVALUATION.md` |
| 12 | Windows 11 hosting | **P** | Scripts written; **not run on Windows**. Linux equivalent verified from a clean clone. |
| 13 | Optional local LLM generator | **V** (mechanics, safety) / not useful at 1.5B | see `docs/MODELS.md` |
| 14 | Production deployment (Vercel + backend) | **N** | Configuration documented; nothing deployed or verified live |
| 15 | GPU inference | **N** | `NYAYA_DEVICE=cuda` exists but is untested (no GPU available) |
| 16 | Email verification / password reset | **N** | needs an email service |
| 17 | Indian data-protection / legal-professional compliance assessment | **N** | explicitly not claimed; flagged in the Privacy page |

## Actual test results (run on this build)

| Check | Result |
|---|---|
| `pytest` (backend, `backend/tests`) | **65 passed** |
| `ruff check .` (backend) | clean |
| `mypy app` | no issues in 38 source files |
| `npm run lint` (eslint, max-warnings 0) | clean |
| `npm run typecheck` (tsc) | clean |
| `npm test` (Vitest) | **17 passed** |
| `npm run build` (frontend production build) | succeeds; JS 282 kB (84 kB gzip), CSS 30 kB |
| Playwright journeys (`e2e/journeys.mjs`) | **13/13 passed in 5 consecutive runs** against a live server with the real corpus and real models (server started with `NYAYA_AUTH_RATE_LIMIT_PER_MINUTE=1000`; with the default 10/min, repeated runs within a minute are correctly throttled and fail on registration) |
| Clean-clone install (`scripts/setup.sh` + pytest) | succeeded (49 tests at that time) |
| Model evaluation | 173-query retrieval benchmark, topic (48), domain (48 vs 20), gate (120+12 vs 20), end-to-end (30), translation (9 languages), resources — all in `docs/EVALUATION.md` |

Defects found and fixed *during* verification (so you know what testing actually caught): section chunks merged under the wrong citation label; an "unsupported quotation" false alarm on valid extractive quotes; a coverage gate too weak to decline off-topic questions; model unload/reload thrash on every query; a hard legal-language gate that rejected valid doctrinal questions; vacuous "citations valid" for uncited generated text; a transient 429 that logged users out; invalid (fork-inherited) memory measurements.

## Known limitations and outstanding dependencies

1. **No statutes are bundled or ingested.** India Code PDF downloads redirected to an error page for automated clients from the build environment, and statute text must not be written from memory. Until you ingest Acts from official PDFs (`docs/INGESTION.md`), the system can only cite the sampled judgments and drafts will report their authorities as "not found in corpus". Statute chunking was tested only on synthetic fixtures; real India Code PDFs may need chunker tuning.
2. **The corpus is a small sample** (60 of ~700+ judgments from one year) and is not auto-updated.
3. **Retrieval benchmark is weak and lexical.** Gold labels come from headnote → cited paragraph; 83% of queries share ≥95% of words with the gold passage. BM25 alone scored highest; the default fuses InLegalBERT (best encoder) as an unproven safety net for paraphrase. Real lay-question → statute retrieval is **unmeasured**.
4. **Gate trade-off.** At the shipped threshold all 20 unrelated test questions are declined and every headnote question is kept, but 2 of 12 doctrinal test questions are declined. A declined question still shows the area of law, urgent contacts, next steps and the closest sources. Near-domain questions the corpus lacks (e.g. tenancy law) are not covered by the calibration sets.
4a. **"Area of law" is general orientation, not retrieval.** It comes from an offence lexicon, a topic classifier (0.81 accuracy on 48 synthetic questions) and a curated list of governing Acts (names only, no section numbers). It can be wrong, is labelled as not drawn from the library, and was checked only on a handful of everyday descriptions. The "nearest sources" for a lay description are often only loosely related because the library is a 60-judgment sample.
5. **Legal-language detector** (CustomInLawBERT) is advisory only; its threshold is corpus-specific.
6. **Published MLM heads** of InLegalBERT and CustomInLawBERT do not work (measured); only encoder outputs are used.
7. **Translation quality is unverified here**; Odia is the weakest language per the model card. No glossary of legal terms or entity protection (`IndicProcessor` placeholders) is implemented, so names/numbers could be altered.
8. **Extractive answers are quotations, not plain-language explanations or application of law to your facts.** The optional LLM did not manage citable output at 1.5B.
9. Rate limiting and background processing are single-process; request timeouts do not cancel running threads.
10. Document facts are regex-based (dates in Indian day-first order; amounts in ₹/Rs/INR); scanned documents require the optional OCR package.
11. The legal-aid directory is the previous product's data (last verified 2024-09-01) and is shown with that date.
12. Not verified: Windows 11 run, PostgreSQL, GPU, Vercel/split hosting, screen-reader accessibility.
