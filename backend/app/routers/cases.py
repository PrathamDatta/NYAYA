from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Case, User
from ..schemas import CaseIn
from ..security import current_user

router = APIRouter(prefix="/cases", tags=["cases"])


def _out(c: Case) -> dict:
    return {"id": c.id, "title": c.title, "narrative": c.narrative, "state": c.state,
            "incident_date": c.incident_date.isoformat() if c.incident_date else None, "facts": c.facts,
            "updated_at": c.updated_at.isoformat()}


def owned_case(db: Session, user: User, case_id: int) -> Case:
    c = db.scalar(select(Case).where(Case.id == case_id, Case.user_id == user.id))
    if not c:
        raise HTTPException(404, "Case not found.")  # 404 (not 403) so ids of other users' cases are not revealed
    return c


@router.get("")
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_out(c) for c in db.scalars(select(Case).where(Case.user_id == user.id).order_by(Case.updated_at.desc()))]


@router.post("", status_code=201)
def create_case(body: CaseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = Case(user_id=user.id, **body.model_dump())
    db.add(c)
    db.commit()
    return _out(c)


@router.get("/{case_id}")
def get_case(case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(owned_case(db, user, case_id))


@router.put("/{case_id}")
def update_case(case_id: int, body: CaseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = owned_case(db, user, case_id)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return _out(c)


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_case(db, user, case_id))
    db.commit()
