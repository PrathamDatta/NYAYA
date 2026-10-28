# Audit of the original application

## Inputs and limits of this audit

* **Live site** (`https://nyaya-bharatha.vercel.app/`): fetched on 2026-10-28 (HTTP 200). It is a client-side Vite/React single-page app (`/assets/index-*.js`, 421 KB). The browser tool in this environment could not drive it interactively, so the audit was done by reading the served HTML and JavaScript bundle. Anything not visible in the bundle is **not** claimed.
* **Repository**: the only commit at the start of this task was `Remove project` — the working tree was empty and history held no earlier code. There was therefore **no source, database, migrations, tests or deployment configuration to audit or preserve**. The bundle was used to recover the product's content and behaviour.

## Findings about the live product

| Area | Finding | Classification |
|---|---|---|
| Backend | None. The bundle makes no API calls (`fetch` appears only in Vite's preload helper). No authentication, no server database. | missing |
| Data storage | `localStorage` only (cases + an audit-log array). Not shared across devices, lost on clearing site data. | partially functional |
| "AI" | No model calls (no OpenAI/Gemini/HF/transformers strings). Case analysis, "20-question adaptive clarification engine", contradiction detection, statute checker and draft generation are rule-based templates and regexes keyed on keywords, with pre-seeded demo cases ("synthetic demonstration data"). | simulated |
| Legal knowledge | A hard-coded list of ~15 Acts with India Code links and canned section explanations (BNS/IPC transition, CPA 2019, Contract Act, TPA…). No retrieval, no source ingestion, no verification. | simulated |
| Document upload | UI claims "PDF, DOCX, image and scan text extraction with SHA-256"; the bundle contains no PDF/OCR library — users paste text. Hashing present. | partially functional (paste only) |
| Drafting | Four templates (police complaint/FIR, legal notice, consumer complaint, civil plaint) rendered from intake fields. Reasonable structure. | functional (static templates) |
| Legal-aid directory | 9 entries (NALSA, SCLSC, Tele-Law, 6 State authorities) with phones, addresses, eligibility and `lastVerifiedDate: 2024-09-01`. Useful content, now >2 years old. | functional, stale |
| Privacy claims | "DPDP Act, 2023 Compliant", "compliant with Indian privacy laws" — unsupported by any assessment. | misleading |
| Tests / deployment | Unknown (no source). Vercel static hosting is evident. | not assessable |

## What was preserved

* The product scope and flow (describe an incident → clarify facts → upload evidence → find inconsistencies → draft a document → find legal aid) and its four drafting templates.
* The legal-aid directory data, recovered verbatim into `backend/app/data/legal_aid_directory.json` **with its original verification dates shown to users**.
* Emergency numbers (112, 181, 1930, 15100).
* The Vite + React + TypeScript + Tailwind stack (so the frontend can stay on Vercel).

## What was not preserved (and why)

* "DPDP compliant" claim — removed; replaced by an explicit statement that compliance has not been assessed.
* Seeded demo cases — removed (they were presented alongside real functionality; synthetic data is now confined to tests and labelled).
* Rule-based "analysis" presented as AI — replaced by retrieval over ingested sources, with honest declines.
* Any existing user data: none was recoverable (it lived only in each visitor's browser).
