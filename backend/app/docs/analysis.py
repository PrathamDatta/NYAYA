"""Document analysis. Extracted facts (pattern-based, with page references) are kept strictly separate from
model-suggested material (related provisions), and uploaded text is treated as untrusted data: it is never executed
and never placed in an LLM prompt."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"], start=1)}
_MON = "|".join(MONTHS) + "|" + "|".join(m[:3] for m in MONTHS)
DATE_PATTERNS = [
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})[a-z]*\.?,?\s+(\d{{4}})\b", re.I),
    re.compile(rf"\b({_MON})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I),
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]
AMOUNT = re.compile(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d{1,2})?)(?:\s?/-)?", re.I)
PARTY_ORG = re.compile(r"\b(M/s\.?\s+[A-Z][\w&.,' -]{2,60}?|[A-Z][\w&.' -]{2,60}?\s(?:Pvt\.?\s?Ltd\.?|Private Limited|Limited|LLP|LLC|Inc\.?))(?=[\s,.;)]|$)")
PARTY_PERSON = re.compile(r"\b(?:Mr|Mrs|Ms|Smt|Shri|Sri|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}")
ROLE = re.compile(r"(?i)(?:(?:M/s\.?\s+)?[A-Z][\w&.' -]{2,60}?)\s*\(?\s*(?:hereinafter|herein after)\s+(?:referred to as|called)\s+[\"“']?(?:the\s+)?([A-Za-z ]{3,30})[\"”']?")
CLAUSE = re.compile(r"(?m)^\s*(?:clause\s+)?(\d{1,2}(?:\.\d{1,2}){0,2})[.)]\s+([A-Z][^\n]{4,200})")
OBLIGATION = re.compile(r"[^.;\n]{0,120}\b(?:shall|must|agrees? to|undertakes? to|is liable to|will pay)\b[^.;\n]{0,160}", re.I)
KEYWORDS_AMOUNT = ["security deposit", "deposit", "rent", "invoice", "total", "price", "refund", "salary", "advance", "loan",
                   "fee", "compensation", "balance", "amount due", "payment"]
KEYWORDS_DATE = ["agreement", "notice", "delivered", "delivery", "handover", "vacat", "invoice", "payment", "terminat", "incident", "purchase"]


def _month(name: str) -> int:
    n = name.lower()
    if n in MONTHS:
        return MONTHS[n]
    return next(v for k, v in MONTHS.items() if k.startswith(n[:3]))


def _iso(m: re.Match, idx: int) -> str | None:
    g = m.groups()
    try:
        if idx == 0:  # 5 July 2024
            d, mo, y = int(g[0]), _month(g[1]), int(g[2])
        elif idx == 1:  # July 5, 2024
            mo, d, y = _month(g[0]), int(g[1]), int(g[2])
        elif idx == 2:  # 05/07/2024 (day first, the Indian convention)
            d, mo, y = int(g[0]), int(g[1]), int(g[2])
        else:  # 2024-07-05
            y, mo, d = int(g[0]), int(g[1]), int(g[2])
        return date(y, mo, d).isoformat()
    except (ValueError, StopIteration):
        return None


def _context(text: str, a: int, b: int, width: int = 90) -> str:
    return re.sub(r"\s+", " ", text[max(0, a - width): b + width]).strip()


def _nearest(keywords: list[str], ctx: str, pos_in_ctx: int) -> str | None:
    low = ctx.lower()
    best, dist = None, 10**9
    for k in keywords:
        for m in re.finditer(re.escape(k), low):
            dd = abs(m.start() - pos_in_ctx)
            if dd < dist:
                best, dist = k, dd
    return best


def analyse_pages(pages: list[dict]) -> dict[str, Any]:
    dates, amounts, parties, clauses, obligations, unreadable = [], [], [], [], [], []
    seen_party: set[str] = set()
    for p in pages:
        text, pg = p["text"], p["page"]
        if len(text.strip()) < 30:
            unreadable.append({"page": pg, "reason": "no extractable text (blank, image-only or unsupported content)"})
            continue
        for i, pat in enumerate(DATE_PATTERNS):
            for m in pat.finditer(text):
                iso = _iso(m, i)
                if iso:
                    ctx = _context(text, m.start(), m.end())
                    dates.append({"value": iso, "raw": m.group(0), "page": pg, "context": ctx,
                                  "label": _nearest(KEYWORDS_DATE, ctx, min(90, m.start()))})
        for m in AMOUNT.finditer(text):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            ctx = _context(text, m.start(), m.end())
            amounts.append({"value": val, "raw": m.group(0).strip(), "page": pg, "context": ctx,
                            "label": _nearest(KEYWORDS_AMOUNT, ctx, min(90, m.start()))})
        for pat in (PARTY_ORG, PARTY_PERSON):
            for m in pat.finditer(text):
                name = re.sub(r"\s+", " ", m.group(0)).strip(" ,.")
                if name.lower() not in seen_party and len(name) > 4:
                    seen_party.add(name.lower())
                    parties.append({"name": name, "page": pg})
        for m in ROLE.finditer(text):
            parties.append({"name": None, "role": m.group(1).strip(), "page": pg})
        for m in CLAUSE.finditer(text):
            clauses.append({"number": m.group(1), "heading": m.group(2).strip()[:160], "page": pg})
        for m in OBLIGATION.finditer(text):
            obligations.append({"text": re.sub(r"\s+", " ", m.group(0)).strip(), "page": pg})
    return {
        "extracted": {"dates": dates[:200], "amounts": amounts[:200], "parties": parties[:60], "clauses": clauses[:200],
                      "obligations": obligations[:60]},
        "unreadable_pages": unreadable,
        "notes": ["Extracted values are produced by pattern matching and may be incomplete or wrong; check them against the original.",
                  "Obligations are sentences containing words like 'shall' or 'must' — they are candidates, not legal conclusions."],
    }


def find_inconsistencies(docs: list[dict]) -> list[dict]:
    """docs: [{'id':, 'name':, 'analysis': {...}}]. Flags same-label amounts/dates that differ ACROSS documents.
    Output is a list of possible inconsistencies for human review; it is not a finding that anyone is wrong."""
    out = []
    for kind, key in (("amount", "amounts"), ("date", "dates")):
        by_label: dict[str, list[tuple[Any, dict, dict]]] = defaultdict(list)
        for d in docs:
            for item in d["analysis"].get("extracted", {}).get(key, []):
                if item.get("label"):
                    by_label[item["label"]].append((item["value"], item, d))
        for label, rows in by_label.items():
            vals = {v for v, _, _ in rows}
            doc_ids = {d["id"] for _, _, d in rows}
            if len(vals) > 1 and len(doc_ids) > 1:
                out.append({"kind": kind, "label": label, "values": sorted(vals, key=str),
                            "occurrences": [{"document_id": d["id"], "document": d["name"], "page": it["page"], "raw": it["raw"],
                                             "context": it["context"]} for _, it, d in rows][:8],
                            "note": "Different values appear near the same term in different documents. This may be a genuine "
                                    "discrepancy or may refer to different things (e.g. gross vs net). Review the originals."})
    return out
