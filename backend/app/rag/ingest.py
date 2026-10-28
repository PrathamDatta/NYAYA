"""Repeatable corpus ingestion with provenance. Re-running is idempotent (content-hash keyed)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..docs.extraction import extract, sniff
from ..models import ChunkEmbedding, LegalChunk, LegalSource
from .chunking import chunk_document, clean_report_text
from .rag_models import embed_texts

log = logging.getLogger("nyaya.ingest")
SCI_BUCKET = "https://indian-supreme-court-judgments.s3.amazonaws.com"
MONTHS = {m: i for i, m in enumerate(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
                                       "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], start=1)}


def _d(v: Any) -> date | None:
    if not v:
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def add_source(db: Session, meta: dict[str, Any], pages: list[str], embed_models: list[str] | None = None) -> tuple[LegalSource | None, str]:
    """Insert (or skip/version) one legal document. Returns (source, action) with action in created|unchanged|new_version."""
    text_all = "\n".join(pages)
    chash = hashlib.sha256(text_all.encode("utf-8")).hexdigest()
    ident, dtype = meta.get("identifier", ""), meta["doc_type"]
    existing = db.scalars(select(LegalSource).where(LegalSource.identifier == ident, LegalSource.doc_type == dtype)
                          .order_by(LegalSource.id)).all() if ident else []
    if any(e.content_hash == chash for e in existing):
        return next(e for e in existing if e.content_hash == chash), "unchanged"
    version = str(len(existing) + 1)
    action = "new_version" if existing else "created"
    for e in existing:
        if e.status != "archived":
            e.status, e.status_note = "archived", f"Replaced by ingested version {version} (a re-ingestion, not a legal supersession)."
    drafts = chunk_document(pages, dtype)
    if not drafts:
        return None, "no_text"
    src = LegalSource(
        doc_type=dtype, title=meta["title"][:500], identifier=ident, authority=meta.get("authority", ""),
        jurisdiction=meta.get("jurisdiction", "India"), source_url=meta.get("source_url", ""),
        publication_date=_d(meta.get("publication_date")), effective_from=_d(meta.get("effective_from")),
        effective_to=_d(meta.get("effective_to")), status=meta.get("status", "unknown"),
        status_note=meta.get("status_note", ""), version=version, content_hash=chash,
        is_synthetic=bool(meta.get("is_synthetic", False)),
    )
    src.chunks = [LegalChunk(ordinal=i, ref_label=d.ref_label, page_start=d.page_start, page_end=d.page_end, text=d.text)
                  for i, d in enumerate(drafts)]
    db.add(src)
    db.flush()
    if embed_models:
        embed_chunks(db, src.chunks, embed_models)
    db.commit()
    return src, action


def embed_chunks(db: Session, chunks: Iterable[LegalChunk], models: list[str], batch: int = 32) -> int:
    from ..ml.registry import SPECS

    chunks = list(chunks)
    n = 0
    for key in models:
        have = set(db.scalars(select(ChunkEmbedding.chunk_id).where(ChunkEmbedding.model_key == key,
                                                                    ChunkEmbedding.chunk_id.in_([c.id for c in chunks]))))
        todo = [c for c in chunks if c.id not in have]
        for lo in range(0, len(todo), batch):
            part = todo[lo:lo + batch]
            vecs = embed_texts(key, [c.text for c in part])
            for c, v in zip(part, vecs):
                db.add(ChunkEmbedding(chunk_id=c.id, model_key=key, model_revision=SPECS[key].revision,
                                      dim=int(v.shape[0]), vector=v.astype(np.float32).tobytes()))
            db.flush()
            n += len(part)
    return n


def embed_missing(db: Session, models: list[str]) -> int:
    chunks = db.scalars(select(LegalChunk).order_by(LegalChunk.id)).all()
    n = embed_chunks(db, chunks, models)
    db.commit()
    return n


def ingest_manifest(db: Session, manifest_path: Path, embed_models: list[str]) -> list[dict]:
    """Manifest: JSON list of {file|url, doc_type, title, identifier, authority, jurisdiction, source_url, ...}.

    `file` is resolved relative to the manifest. Use this for Acts downloaded from India Code / the Gazette:
    the manifest is where provenance and *verified* status/effective dates are recorded."""
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    report: list[dict[str, Any]] = []
    for e in entries:
        try:
            if e.get("file"):
                data = (manifest_path.parent / e["file"]).read_bytes()
                name = e["file"]
            else:
                r = requests.get(e["url"], timeout=60)
                r.raise_for_status()
                data, name = r.content, e["url"]
            kind = sniff(data, name if "." in name else name + ".pdf")
            pages = [p.text for p in extract(data, kind, max_pages=2000)]
            if e["doc_type"] in ("judgment",):
                pages = [clean_report_text(p) for p in pages]
            meta = {**e, "source_url": e.get("source_url") or e.get("url", "")}
            src, action = add_source(db, meta, pages, embed_models)
            report.append({"title": e["title"], "action": action, "chunks": len(src.chunks) if src else 0})
        except Exception as ex:  # noqa: BLE001 - report per-entry failures, keep going
            db.rollback()
            report.append({"title": e.get("title"), "action": "failed", "error": f"{type(ex).__name__}: {ex}"})
    return report


def _list_sci(year: int, limit: int, offset: int) -> list[str]:
    keys: list[str] = []
    token = None
    while len(keys) < limit + offset:
        params = {"list-type": "2", "prefix": f"data/pdf/year={year}/english/", "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        r = requests.get(SCI_BUCKET + "/", params=params, timeout=60)
        r.raise_for_status()
        keys += re.findall(r"<Key>([^<]+\.pdf)</Key>", r.text)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
        if not m:
            break
        token = m.group(1)
    return keys[offset: offset + limit]


_HDR = re.compile(r"(?i)(?:digital\s+)?supreme\s+court\s+reports|\[\d{4}\]\s*\d+\s*S\.C\.R\.?(?:\s*\d+)?(?:\s*:\s*\d{4}\s+INSC\s+\d+)?|\b\d{4}\s+INSC\s+\d+")


def clean_title(t: str) -> str:
    t = _HDR.sub(" ", t)
    t = re.sub(r"(?i)^\s*(?:case details|headnote)\s*[:\-]?\s*", "", t)
    t = re.sub(r"^\s*\d{1,4}\s+(?=[A-Z])", "", t)
    return re.sub(r"\s+", " ", t).strip(" :-") or "Supreme Court of India judgment"


def parse_sci_first_page(text: str) -> tuple[str, date | None]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title_lines: list[str] = []
    dt: date | None = None
    for ln in lines:
        m = re.match(r"(?i)^(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{1,2}),\s*(\d{4})", ln)
        if m:
            dt = date(int(m.group(3)), MONTHS[m.group(1).upper()], int(m.group(2)))
            break
        if re.fullmatch(r"\d{1,4}|[A-H]", ln) or len(title_lines) > 8:
            continue
        title_lines.append(ln)
    return clean_title(" ".join(title_lines)), dt


def ingest_sci(db: Session, year: int, limit: int, offset: int, embed_models: list[str]) -> list[dict]:
    """Ingest English Supreme Court judgments from the public dataset built from the Court's own publications."""
    report: list[dict[str, Any]] = []
    for key in _list_sci(year, limit, offset):
        stem = key.rsplit("/", 1)[-1].removesuffix("_EN.pdf")
        url = f"{SCI_BUCKET}/{key}"
        try:
            data = requests.get(url, timeout=120).content
            pages = extract(data, "pdf", max_pages=800)
            raw_pages = [p.text for p in pages]
            if sum(len(t) for t in raw_pages) < 500:
                report.append({"key": key, "action": "skipped_no_text_layer"})
                continue
            title, dt = parse_sci_first_page(raw_pages[0])
            nc = ""
            try:
                md = requests.get(f"{SCI_BUCKET}/metadata/json/year={year}/{stem}.json", timeout=30).json()
                nc = re.sub(r"^(\d{4})([A-Z]+)(\d+)$", r"\1 \2 \3", md.get("nc_display", ""))
            except Exception:  # noqa: BLE001 - metadata is optional
                pass
            meta: dict[str, Any] = {"doc_type": "judgment", "title": title, "identifier": nc or stem, "authority": "Supreme Court of India",
                    "jurisdiction": "India", "source_url": url, "publication_date": dt, "status": "in_force"}
            src, action = add_source(db, meta, [clean_report_text(t) for t in raw_pages], embed_models)
            report.append({"key": key, "title": title[:90], "action": action, "chunks": len(src.chunks) if src else 0})
        except Exception as ex:  # noqa: BLE001
            db.rollback()
            report.append({"key": key, "action": "failed", "error": f"{type(ex).__name__}: {ex}"})
    return report
