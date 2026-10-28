from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import AuthSession, Case, Conversation, Draft, UploadedDocument, User
from ..schemas import Credentials, Login, UserOut
from ..security import COOKIE, _digest, audit, create_session, current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(resp: Response, token: str) -> None:
    s = get_settings()
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=s.cookie_secure, max_age=s.session_ttl_hours * 3600, path="/")


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: Credentials, resp: Response, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists.")
    u = User(email=body.email, password_hash=hash_password(body.password), display_name=body.display_name.strip())
    db.add(u)
    db.commit()
    _set_cookie(resp, create_session(db, u))
    audit(db, u.id, "register")
    return u


@router.post("/login", response_model=UserOut)
def login(body: Login, resp: Response, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    ok = verify_password(body.password, u.password_hash) if u else verify_password(body.password, "scrypt$AAAA$AAAA")
    if not u or not ok:
        raise HTTPException(401, "Email or password is incorrect.")  # same message either way: no account enumeration
    _set_cookie(resp, create_session(db, u))
    audit(db, u.id, "login")
    return u


@router.post("/logout", status_code=204)
def logout(request: Request, resp: Response, db: Session = Depends(get_db)):
    tok = request.cookies.get(COOKIE)
    if tok:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _digest(tok)))
        db.commit()
    resp.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything the platform stores about the signed-in user (data portability)."""
    convs = db.scalars(select(Conversation).where(Conversation.user_id == user.id)).all()
    return {
        "user": {"email": user.email, "display_name": user.display_name, "created_at": user.created_at.isoformat()},
        "cases": [{"id": c.id, "title": c.title, "narrative": c.narrative, "state": c.state, "facts": c.facts} for c in db.scalars(select(Case).where(Case.user_id == user.id))],
        "conversations": [{"id": c.id, "title": c.title, "messages": [{"role": m.role, "content": m.content, "payload": m.payload} for m in c.messages]} for c in convs],
        "documents": [{"id": d.id, "name": d.original_name, "sha256": d.sha256, "status": d.status, "analysis": d.analysis} for d in db.scalars(select(UploadedDocument).where(UploadedDocument.user_id == user.id))],
        "drafts": [{"id": d.id, "title": d.title, "template": d.template_id, "facts": d.facts, "content": d.content} for d in db.scalars(select(Draft).where(Draft.user_id == user.id))],
    }


@router.delete("/account", status_code=204)
def delete_account(resp: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Irreversibly deletes the account, all rows owned by it and its uploaded files from disk."""
    folder = get_settings().upload_path / str(user.id)
    audit(db, None, "account_deleted", f"user_id={user.id}")
    db.delete(user)  # ON DELETE CASCADE removes sessions, cases, conversations, documents, drafts
    db.commit()
    shutil.rmtree(folder, ignore_errors=True)
    resp.delete_cookie(COOKIE, path="/")
