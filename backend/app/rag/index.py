"""In-memory hybrid index over the ingested corpus (BM25 + one dense matrix per encoder).

Justification for not using pgvector by default: the corpus a laptop deployment holds is thousands to low
hundreds of thousands of passages, exact cosine search over a float32 matrix is exact and fast at that size,
and it keeps the install to a single process with SQLite. The schema stores vectors portably, so a pgvector
column can replace the matrix when the corpus outgrows RAM (see docs/ARCHITECTURE.md).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ChunkEmbedding, LegalChunk, LegalSource
from .textutil import BM25, tokens

MODEL_KEYS = ("inlegalbert", "incaselawbert", "custominlawbert")


@dataclass
class Hit:
    chunk_id: int
    source_id: int
    score: float
    text: str
    ref_label: str
    page_start: int | None
    page_end: int | None
    source: dict[str, Any]
    ranks: dict[str, int] = field(default_factory=dict)
    raw: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {"chunk_id": self.chunk_id, "score": round(self.score, 5), "text": self.text, "ref_label": self.ref_label,
                "page_start": self.page_start, "page_end": self.page_end, "source": self.source,
                "ranks": self.ranks, "warnings": self.warnings}


def source_validity(src: dict[str, Any], as_of: date, include_historical: bool) -> tuple[bool, str | None]:
    """Temporal validation. Only verified status information stored at ingestion is used; nothing is inferred."""
    ef, et = src.get("effective_from"), src.get("effective_to")
    if src["doc_type"] == "judgment":  # judgments are precedent, not 'in force'; still show their date
        return True, None
    if src["status"] == "archived" and not include_historical:
        return False, "older ingested version"
    if src["status"] == "repealed" and not include_historical:
        return False, "repealed"
    if et and et < as_of and not include_historical:
        return False, f"no longer in force since {et.isoformat()}"
    if ef and ef > as_of and not include_historical:
        return False, f"not yet in force (commences {ef.isoformat()})"
    if src["status"] == "superseded":
        return True, "marked superseded; check the current provision" + (f" ({src['status_note']})" if src.get("status_note") else "")
    if src["status"] == "unknown":
        return True, "in-force status not verified at ingestion"
    return True, None


class CorpusIndex:
    def __init__(self) -> None:
        self.chunk_ids: list[int] = []
        self.meta: list[dict[str, Any]] = []
        self.sources: dict[int, dict[str, Any]] = {}
        self.bm25: BM25 | None = None
        self.mats: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}  # key -> (centred matrix, has_vec, mean)
        self.raw: dict[str, np.ndarray] = {}  # key -> uncentred normalised matrix (kept for evaluation)
        self.stamp: tuple | None = None

    @staticmethod
    def current_stamp(db: Session) -> tuple:
        return (
            db.scalar(select(func.count(LegalChunk.id))), db.scalar(select(func.max(LegalChunk.id))),
            db.scalar(select(func.count(ChunkEmbedding.id))), db.scalar(select(func.count(LegalSource.id))),
        )

    def load(self, db: Session) -> None:
        rows = db.execute(select(LegalChunk, LegalSource).join(LegalSource, LegalSource.id == LegalChunk.source_id)
                          .order_by(LegalChunk.id)).all()
        self.chunk_ids, self.meta, self.sources = [], [], {}
        for ch, src in rows:
            self.chunk_ids.append(ch.id)
            self.meta.append({"text": ch.text, "ref_label": ch.ref_label, "page_start": ch.page_start,
                              "page_end": ch.page_end, "source_id": src.id})
            self.sources[src.id] = {
                "id": src.id, "doc_type": src.doc_type, "title": src.title, "identifier": src.identifier,
                "authority": src.authority, "jurisdiction": src.jurisdiction, "source_url": src.source_url,
                "publication_date": src.publication_date, "effective_from": src.effective_from,
                "effective_to": src.effective_to, "status": src.status, "status_note": src.status_note,
                "version": src.version, "is_synthetic": src.is_synthetic, "ingested_at": src.ingested_at.isoformat(),
            }
        self.bm25 = BM25([tokens(m["text"] + " " + m["ref_label"]) for m in self.meta])
        pos = {cid: i for i, cid in enumerate(self.chunk_ids)}
        self.mats, self.raw = {}, {}
        for key in MODEL_KEYS:
            embs = db.execute(select(ChunkEmbedding.chunk_id, ChunkEmbedding.vector, ChunkEmbedding.dim)
                              .where(ChunkEmbedding.model_key == key)).all()
            if not embs:
                continue
            dim = embs[0].dim
            mat = np.zeros((len(self.chunk_ids), dim), dtype=np.float32)
            has = np.zeros(len(self.chunk_ids), dtype=bool)
            for cid, vec, _ in embs:
                i = pos.get(cid)
                if i is not None:
                    mat[i] = np.frombuffer(vec, dtype=np.float32)
                    has[i] = True
            self.raw[key] = mat
            mean = mat[has].mean(0) if has.any() else np.zeros(dim, dtype=np.float32)
            centred = mat - mean  # BERT vectors are anisotropic; centre with corpus mean, then re-normalise
            n = np.linalg.norm(centred, axis=1, keepdims=True)
            centred = centred / np.maximum(n, 1e-9)
            centred[~has] = 0
            self.mats[key] = (centred, has, mean)
        self.stamp = None

    def ensure_fresh(self, db: Session) -> None:
        st = self.current_stamp(db)
        if st != self.stamp:
            self.load(db)
            self.stamp = st

    def dense_scores(self, key: str, qvec_raw: np.ndarray) -> np.ndarray | None:
        if key not in self.mats:
            return None
        mat, has, mean = self.mats[key]
        q = qvec_raw - mean
        q = q / max(float(np.linalg.norm(q)), 1e-9)
        s = mat @ q
        s[~has] = -1.0
        return s


_index = CorpusIndex()
_lock = threading.RLock()


def get_index(db: Session) -> CorpusIndex:
    with _lock:
        _index.ensure_fresh(db)
        return _index


def reset_index() -> None:
    with _lock:
        _index.stamp = None
        _index.chunk_ids = []
