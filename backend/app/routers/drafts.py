from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..docs import drafting
from ..models import Draft, DraftRevision, User
from ..schemas import DraftIn, DraftUpdate
from ..security import current_user
from .cases import owned_case

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _out(d: Draft, db: Session | None = None) -> dict:
    o = {"id": d.id, "template_id": d.template_id, "title": d.title, "facts": d.facts, "content": d.content, "case_id": d.case_id,
         "updated_at": d.updated_at.isoformat(), "revisions": len(d.revisions)}
    o["missing"] = [f["label"] for f in drafting.TEMPLATES[d.template_id]["fields"] if f["required"] and not (d.facts.get(f["key"]) or "").strip()]
    if db is not None:
        o["authorities"] = drafting.check_authorities(db, d.template_id)
    return o


def _owned(db: Session, user: User, did: int) -> Draft:
    d = db.scalar(select(Draft).where(Draft.id == did, Draft.user_id == user.id))
    if not d:
        raise HTTPException(404, "Draft not found.")
    return d


@router.get("/templates")
def templates():
    return drafting.public_templates()


@router.get("")
def list_drafts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_out(d) for d in db.scalars(select(Draft).where(Draft.user_id == user.id).order_by(Draft.updated_at.desc()))]


@router.post("", status_code=201)
def create(body: DraftIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.template_id not in drafting.TEMPLATES:
        raise HTTPException(422, "Unknown template.")
    if body.case_id:
        owned_case(db, user, body.case_id)
    content, _ = drafting.render(body.template_id, body.facts)
    d = Draft(user_id=user.id, case_id=body.case_id, template_id=body.template_id, title=drafting.TEMPLATES[body.template_id]["title"],
              facts=body.facts, content=content)
    d.revisions.append(DraftRevision(content=content))
    db.add(d)
    db.commit()
    return _out(d, db)


@router.get("/{did}")
def get(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(_owned(db, user, did), db)


@router.put("/{did}")
def update(did: int, body: DraftUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _owned(db, user, did)
    if body.title is not None:
        d.title = body.title
    if body.facts is not None:  # re-render from facts; user edits are kept as a revision first
        d.revisions.append(DraftRevision(content=d.content))
        d.facts = body.facts
        d.content, _ = drafting.render(d.template_id, body.facts)
    if body.content is not None:
        d.revisions.append(DraftRevision(content=d.content))
        d.content = body.content
    db.commit()
    return _out(d, db)


@router.delete("/{did}", status_code=204)
def delete(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, did))
    db.commit()


@router.get("/{did}/export")
def export(did: int, format: str = Query("docx", pattern="^(docx|txt)$"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _owned(db, user, did)
    auths = drafting.check_authorities(db, d.template_id)
    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", d.title) or "draft"
    if format == "txt":
        tail = "\n\n--- Verification checklist ---\n" + "\n".join(f"{a['authority']}: {'found in corpus' if a['verified_in_corpus'] else 'NOT verified'}" for a in auths)
        return Response((d.content + tail).encode("utf-8"), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.txt"'})
    return Response(drafting.to_docx(d.title, d.content, auths),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.docx"'})
