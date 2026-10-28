from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/aid", tags=["legal-aid"])
DATA = Path(__file__).resolve().parents[1] / "data" / "legal_aid_directory.json"


@lru_cache
def _load() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))


@router.get("/directory")
def directory(q: str = Query("", max_length=100), kind: str = Query("", max_length=20)) -> dict:
    items = _load()
    ql = q.lower().strip()
    if ql:
        items = [i for i in items if ql in json.dumps(i, ensure_ascii=False).lower()]
    if kind:
        items = [i for i in items if i["type"] == kind]
    return {"items": items, "count": len(items),
            "provenance": "Carried over from the previous version of Nyaya Bharatha. Each entry shows the date it was last verified; "
                          "contact details may have changed, so confirm on the official website before relying on them."}
