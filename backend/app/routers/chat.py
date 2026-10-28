from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..ml.translation import IndicTranslationService, UnsupportedLanguageError
from ..models import Conversation, Message, User
from ..rag.pipeline import LegalResponsePipeline
from ..rag.retriever import Filters
from ..schemas import AskIn, TranslateIn
from ..security import current_user, inference_gate
from .cases import owned_case

router = APIRouter(tags=["chat"])
pipeline = LegalResponsePipeline()


def _run_gated(fn, *a):  # noqa: ANN001, ANN202
    if not inference_gate.acquire(timeout=5):
        raise HTTPException(503, "The model service is busy. Please retry in a moment.")
    try:
        return fn(*a)
    finally:
        inference_gate.release()


@router.post("/ask")
async def ask(body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.translate_to and body.translate_to not in IndicTranslationService.languages():
        raise HTTPException(422, f"Unsupported language '{body.translate_to}'. Supported: {', '.join(IndicTranslationService.languages())}")
    conv: Conversation | None = None
    if body.conversation_id:
        conv = db.scalar(select(Conversation).where(Conversation.id == body.conversation_id, Conversation.user_id == user.id))
        if not conv:
            raise HTTPException(404, "Conversation not found.")
    if body.case_id:
        owned_case(db, user, body.case_id)
    if conv is None:
        conv = Conversation(user_id=user.id, case_id=body.case_id, title=body.question[:80])
        db.add(conv)
        db.flush()
    db.add(Message(conversation_id=conv.id, role="user", content=body.question))
    db.commit()

    filters = Filters(doc_types=body.doc_types, as_of=body.as_of, include_historical=body.include_historical)
    try:
        resp = await asyncio.wait_for(run_in_threadpool(_run_gated, pipeline.answer, db, body.question, filters),
                                      timeout=get_settings().request_timeout_s)
    except asyncio.TimeoutError:
        raise HTTPException(504, "The request took too long. Please try a shorter question.")
    if body.translate_to and resp.get("answer"):
        # Translate only the plain-language framing, never quotations; label the output as machine translation.
        parts = [resp["answer_note"], *resp["sections"]["next_steps"][:3]]
        try:
            tr = await run_in_threadpool(_run_gated, IndicTranslationService().translate, "\n".join(parts), body.translate_to)
            resp["translation"] = tr
        except Exception as e:  # noqa: BLE001 - translation is optional; report why it is missing
            resp["translation_error"] = str(e)
    db.add(Message(conversation_id=conv.id, role="assistant", content=resp.get("answer") or resp.get("message") or "", payload=resp))
    db.commit()
    return {"conversation_id": conv.id, **resp}


@router.post("/translate")
async def translate(body: TranslateIn, user: User = Depends(current_user)):
    try:
        return await run_in_threadpool(_run_gated, IndicTranslationService().translate, body.text, body.target)
    except UnsupportedLanguageError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/conversations")
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id.desc()).limit(100))
    return [{"id": c.id, "title": c.title, "case_id": c.case_id, "created_at": c.created_at.isoformat()} for c in rows]


@router.get("/conversations/{cid}")
def conversation(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.scalar(select(Conversation).where(Conversation.id == cid, Conversation.user_id == user.id))
    if not c:
        raise HTTPException(404, "Conversation not found.")
    return {"id": c.id, "title": c.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "payload": m.payload,
                                                         "created_at": m.created_at.isoformat()} for m in c.messages]}


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.scalar(select(Conversation).where(Conversation.id == cid, Conversation.user_id == user.id))
    if not c:
        raise HTTPException(404, "Conversation not found.")
    db.delete(c)
    db.commit()
