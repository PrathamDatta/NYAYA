from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import LegalChunk, LegalSource
from ..rag.retriever import Filters, LegalRetriever
from ..security import inference_gate

router = APIRouter(prefix="/library", tags=["library"])
retriever = LegalRetriever()


def _src(s: LegalSource) -> dict:
    return {"id": s.id, "doc_type": s.doc_type, "title": s.title, "identifier": s.identifier, "authority": s.authority,
            "jurisdiction": s.jurisdiction, "source_url": s.source_url, "publication_date": s.publication_date.isoformat() if s.publication_date else None,
            "effective_from": s.effective_from.isoformat() if s.effective_from else None, "status": s.status, "status_note": s.status_note,
            "version": s.version, "synthetic": s.is_synthetic, "ingested_at": s.ingested_at.isoformat()}


@router.get("/search")
async def search(q: str = Query(min_length=2, max_length=500), doc_type: list[str] | None = Query(None),
                 year_from: int | None = Query(None, ge=1800, le=2100), year_to: int | None = Query(None, ge=1800, le=2100),
                 as_of: date | None = None, include_historical: bool = False, limit: int = Query(10, ge=1, le=30),
                 db: Session = Depends(get_db)):
    """Public search over the ingested legal corpus (hybrid lexical + Law-AI encoder retrieval)."""
    def run():  # noqa: ANN202
        if not inference_gate.acquire(timeout=5):
            raise HTTPException(503, "The search service is busy. Please retry in a moment.")
        try:
            return retriever.search(db, q, Filters(doc_types=doc_type, year_from=year_from, year_to=year_to, as_of=as_of,
                                                   include_historical=include_historical), top_k=limit)
        finally:
            inference_gate.release()

    hits, info = await run_in_threadpool(run)
    return {"query": q, "results": [h.public() for h in hits], "info": info}


@router.get("/sources")
def sources(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), doc_type: str | None = None,
            q: str | None = Query(None, max_length=200), db: Session = Depends(get_db)):
    stmt = select(LegalSource).where(LegalSource.status != "archived", LegalSource.is_synthetic.is_(False))
    if doc_type:
        stmt = stmt.where(LegalSource.doc_type == doc_type)
    if q:
        stmt = stmt.where(func.lower(LegalSource.title).contains(q.lower()) | func.lower(LegalSource.identifier).contains(q.lower()))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(LegalSource.publication_date.desc().nullslast(), LegalSource.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_src(s) for s in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/sources/{sid}")
def source(sid: int, db: Session = Depends(get_db)):
    s = db.get(LegalSource, sid)
    if not s or s.is_synthetic:
        raise HTTPException(404, "Source not found.")
    n = db.scalar(select(func.count(LegalChunk.id)).where(LegalChunk.source_id == sid))
    return {**_src(s), "chunks": n}
