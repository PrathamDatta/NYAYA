from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal, get_db
from ..docs import analysis
from ..docs.extraction import ExtractionError, OcrUnavailableError, extract, sniff
from ..models import UploadedDocument, User
from ..security import audit, current_user
from .cases import owned_case

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger("nyaya.documents")


def _out(d: UploadedDocument, full: bool = False) -> dict:
    o = {"id": d.id, "name": d.original_name, "size_bytes": d.size_bytes, "sha256": d.sha256, "status": d.status, "error": d.error,
         "case_id": d.case_id, "created_at": d.created_at.isoformat(), "pages": len(d.pages or [])}
    if full:
        o["pages_text"] = d.pages
        o["analysis"] = d.analysis
    return o


def process_document(doc_id: int) -> None:
    """Runs after the upload response. Failures are recorded on the row, never swallowed silently."""
    from ..ml.registry import ModelUnavailableError
    from ..rag.retriever import Filters, LegalRetriever

    db = SessionLocal()
    try:
        d = db.get(UploadedDocument, doc_id)
        if not d:
            return
        d.status = "processing"
        db.commit()
        path = get_settings().upload_path / str(d.user_id) / d.storage_name
        try:
            data = path.read_bytes()
            kind = sniff(data, d.original_name)
            pages = extract(data, kind, get_settings().max_pages)
            d.pages = [{"page": p.page, "text": p.text, "method": p.method} for p in pages]
            result = analysis.analyse_pages(d.pages)
            if not any(p.text.strip() for p in pages):
                raise ExtractionError("No text could be extracted from this document.")
            related, err = [], None
            try:  # model-suggested material is stored apart from extracted facts
                sample = " ".join(p.text for p in pages)[:1500]
                hits, _ = LegalRetriever().search(db, sample, Filters(), top_k=4)
                related = [{"title": h.source["title"], "ref": h.ref_label, "url": h.source["source_url"], "score": round(h.score, 4),
                            "excerpt": h.text[:300]} for h in hits]
            except ModelUnavailableError as e:
                err = e.reason
            result["related_provisions"] = {"items": related, "error": err,
                                            "note": "Suggested by retrieval models from the document's opening text; not a legal conclusion."}
            d.analysis, d.status, d.error = result, "done", ""
        except OcrUnavailableError as e:
            d.status, d.error = "failed", str(e)
        except ExtractionError as e:
            d.status, d.error = "failed", str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("document processing failed (id=%s)", doc_id)
            d.status, d.error = "failed", f"Processing failed ({type(e).__name__})."
        d.processed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


@router.post("", status_code=202)
async def upload(background: BackgroundTasks, file: UploadFile = File(...), case_id: int | None = Form(None),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = get_settings()
    if case_id:
        owned_case(db, user, case_id)
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {s.max_upload_mb} MB limit.")
    if not data:
        raise HTTPException(422, "The file is empty.")
    name = (file.filename or "document")[:200].replace("\\", "/").rsplit("/", 1)[-1]
    try:
        sniff(data, name)  # validate by content, reject early
    except ExtractionError as e:
        raise HTTPException(415, str(e))
    storage = secrets.token_hex(16)
    folder = s.upload_path / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / storage).write_bytes(data)
    d = UploadedDocument(user_id=user.id, case_id=case_id, original_name=name, mime=file.content_type or "", size_bytes=len(data),
                         sha256=hashlib.sha256(data).hexdigest(), storage_name=storage)
    db.add(d)
    db.commit()
    audit(db, user.id, "document_uploaded", f"doc={d.id} size={len(data)}")  # no filename or content in the audit log
    background.add_task(process_document, d.id)
    return _out(d)


def _owned(db: Session, user: User, doc_id: int) -> UploadedDocument:
    d = db.scalar(select(UploadedDocument).where(UploadedDocument.id == doc_id, UploadedDocument.user_id == user.id))
    if not d:
        raise HTTPException(404, "Document not found.")
    return d


@router.get("")
def list_documents(case_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(UploadedDocument).where(UploadedDocument.user_id == user.id)
    if case_id:
        stmt = stmt.where(UploadedDocument.case_id == case_id)
    return [_out(d) for d in db.scalars(stmt.order_by(UploadedDocument.id.desc()))]


@router.get("/inconsistencies")
def inconsistencies(case_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(UploadedDocument).where(UploadedDocument.user_id == user.id, UploadedDocument.status == "done")
    if case_id:
        stmt = stmt.where(UploadedDocument.case_id == case_id)
    docs = [{"id": d.id, "name": d.original_name, "analysis": d.analysis} for d in db.scalars(stmt)]
    return {"documents": len(docs), "items": analysis.find_inconsistencies(docs)}


@router.get("/{doc_id}")
def get_document(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(_owned(db, user, doc_id), full=True)


@router.post("/{doc_id}/retry", status_code=202)
def retry(doc_id: int, background: BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _owned(db, user, doc_id)
    d.status, d.error = "queued", ""
    db.commit()
    background.add_task(process_document, d.id)
    return _out(d)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _owned(db, user, doc_id)
    (get_settings().upload_path / str(user.id) / d.storage_name).unlink(missing_ok=True)
    db.delete(d)
    db.commit()
