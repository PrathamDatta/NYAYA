from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..ml import registry
from ..ml.translation import IndicTranslationService
from ..models import LegalChunk, LegalSource

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    n = db.scalar(select(func.count(LegalChunk.id))) or 0
    return {"status": "ready", "database": "ok", "corpus_chunks": n}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    by_type = db.execute(select(LegalSource.doc_type, LegalSource.is_synthetic, func.count(LegalSource.id)).group_by(LegalSource.doc_type, LegalSource.is_synthetic)).all()
    return {
        "models": registry.status(),
        "generator_backend": s.generator_backend,
        "translation_languages": IndicTranslationService.languages(),
        "device": s.device,
        "corpus": {"sources": [{"doc_type": t, "synthetic": syn, "count": c} for t, syn, c in by_type],
                   "chunks": db.scalar(select(func.count(LegalChunk.id))) or 0},
        "limits": {"max_upload_mb": s.max_upload_mb, "max_pages": s.max_pages},
    }
