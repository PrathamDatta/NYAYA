from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuditEvent, AuthSession, User

COOKIE = "nyaya_session"
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, maxmem=64 * 1024 * 1024, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        dk = hashlib.scrypt(pw.encode(), salt=base64.b64decode(s), maxmem=64 * 1024 * 1024, **_SCRYPT)
        return hmac.compare_digest(dk, base64.b64decode(h))
    except Exception:  # noqa: BLE001
        return False


def _digest(token: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(hours=get_settings().session_ttl_hours)
    db.add(AuthSession(token_hash=_digest(token), user_id=user.id, expires_at=exp))
    db.commit()
    return token


def user_from_request(request: Request, db: Session) -> User | None:
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    sess = db.scalar(select(AuthSession).where(AuthSession.token_hash == _digest(tok)))
    if not sess:
        return None
    exp = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        db.delete(sess)
        db.commit()
        return None
    return db.get(User, sess.user_id)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    u = user_from_request(request, db)
    if not u:
        raise HTTPException(401, "Please sign in.")
    return u


def audit(db: Session, user_id: int | None, action: str, detail: str = "") -> None:
    db.add(AuditEvent(user_id=user_id, action=action, detail=detail[:300]))
    db.commit()


class RateLimiter:
    """Sliding-window limiter, per process. For multi-process deployments put it behind a proxy limiter or Redis."""

    def __init__(self) -> None:
        self.hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, ip: str, bucket: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[(ip, bucket)]
            while q and q[0] < now - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


limiter = RateLimiter()
inference_gate = threading.BoundedSemaphore(2)  # cap concurrent model inference (laptop memory protection)
