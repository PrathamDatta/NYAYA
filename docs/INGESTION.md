# Legal corpus ingestion and updates

The corpus is **not** continuously updated. It contains exactly what you have ingested, with the provenance you recorded.
Re-run ingestion to refresh it; ingestion is idempotent (keyed by content hash) and keeps older versions as `archived`.

## What is bundled vs what you must supply

| Source | How it is loaded | Status in this repository |
|---|---|---|
| Supreme Court of India judgments (English) | `ingest-sci` from the public open dataset built from the Court's publications (`indian-supreme-court-judgments.s3.amazonaws.com`) | Pipeline implemented and run on a sample (see `docs/EVALUATION.md` for the exact counts). |
| Central Acts, Rules, Gazette notifications (India Code, legislative.gov.in, egazette) | `ingest-manifest` with PDFs **you download** from the official site | Pipeline implemented and unit-tested on synthetic fixtures. **No real statutes are bundled**: India Code's PDF links redirect to an error page for automated clients from the build environment, and statute text must never be typed from memory. |
| High Court judgments | `ingest-manifest` (PDF + metadata) | Pipeline supports them; none loaded. |

Terms of use: check each portal's terms before bulk downloading. The SC dataset page lists its licence/terms.

## Supreme Court judgments

```bash
python -m app.cli ingest-sci --year 2023 --limit 60            # embeds with all three encoders (CPU: roughly 40-60 s per judgment)
python -m app.cli ingest-sci --year 2023 --limit 60 --offset 60 # next batch
python -m app.cli corpus                                         # counts
```

Notes: only judgments with a text layer are ingested (scanned ones are reported as `skipped_no_text_layer`). Titles and dates are parsed from page 1; the neutral citation comes from the dataset metadata. SCR-reported judgments begin with an **editorial headnote**: it is labelled `Preamble / headnote` and must not be read as the Court's own words.

## Acts and rules (manifest)

1. Open the Act's page on https://www.indiacode.nic.in and download the official PDF into `corpus/downloads/`.
2. Add an entry to a manifest (see `corpus/manifest.example.json`). Fill in **only what you have verified**:
   `effective_from`, `effective_to`, `status` (`in_force | repealed | superseded | unknown`) and `status_note`. If unsure leave `status: "unknown"`; answers will then say the in-force status is unverified.
3. Run:
   ```bash
   python -m app.cli ingest-manifest corpus/manifest.json
   ```
4. Check how the chunker split the Act (`Section N — Title`): India Code PDFs vary. If a PDF has few detectable section headings it falls back to paragraph windows and labels them `Passage N`. Inspect results in the Library → Browse sources and search a few sections you know.

### Amendments, repeals and old↔new law (IPC→BNS etc.)

Nothing is inferred. Mapping an old provision to a new one is **not** a one-to-one lookup, so no mapping table is shipped. Record repeals/supersession in `status`/`status_note` only from the official text (e.g. the repeal and savings section of the new Act); mark transitional rules in `status_note`.

## Updating

Run the same commands again. Unchanged documents are skipped; changed ones create version N+1 and the previous version becomes `archived` (hidden from search unless "Include historical" is ticked). `python -m app.cli embed` embeds any chunks that lack vectors for a model (e.g. after adding a model to `--models`).

## Embedding vectors

Vectors are stored per chunk and per model (`chunk_embeddings`: model key, **pinned model revision**, dim, float32 bytes). If a model revision is ever changed, re-embed (delete rows for that model, run `embed`) — mixed revisions in one index are not supported.
