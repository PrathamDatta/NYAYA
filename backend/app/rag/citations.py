"""CitationValidator: every citation marker, quotation and URL in a response must be traceable to a retrieved passage."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_MARK = re.compile(r"\[S(\d+)\]")
_URL = re.compile(r"https?://[^\s)\]>\"']+")
_SEC = re.compile(r"(?i)\b(?:section|sec\.|s\.)\s*(\d{1,3}[A-Z]{0,2})(?:\s*\(\w+\))*\s+of\s+(?:the\s+)?([A-Z][A-Za-z ,]{3,60}?(?:Act|Sanhita|Adhiniyam|Code)(?:,?\s*\d{4})?)")


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@dataclass
class Report:
    cleaned: str
    total_citations: int = 0
    valid_citations: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def validity(self) -> float:
        return 1.0 if self.total_citations == 0 else self.valid_citations / self.total_citations

    def public(self) -> dict:
        return {"total": self.total_citations, "valid": self.valid_citations, "validity": round(self.validity, 4), "issues": self.issues}


class CitationValidator:
    def __init__(self, passages: list[dict]):
        """passages: [{'n': 1, 'text': ..., 'url': ...}] in the order they were shown to the generator."""
        self.by_n = {p["n"]: p for p in passages}
        self.allowed_urls = {p["url"] for p in passages if p.get("url")}
        self.corpus_norm = _norm(" ".join(p["text"] for p in passages))

    def quote_supported(self, n: int, quote: str) -> bool:
        """Every segment (split on the elision marker […]) must occur verbatim in the cited passage."""
        p = self.by_n.get(n)
        if not p:
            return False
        segs = [seg for seg in re.split(r"\[…\]|\[\.\.\.\]", quote) if _norm(seg)]
        return bool(segs) and all(len(_norm(seg)) >= 8 and _norm(seg) in _norm(p["text"]) for seg in segs)

    def require_citations(self, text: str) -> tuple[str, list[str]]:
        """For free-text (generated) answers: keep only sentences carrying at least one valid [S#] marker.

        Returns (kept_text, dropped_sentences). An uncited generated claim is not 'verified' just because it has no citations to fail."""
        kept: list[str] = []
        dropped: list[str] = []
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+", text):
            sent = sent.strip()
            if not sent:
                continue
            marks = [int(m) for m in _MARK.findall(sent)]
            (kept if marks and all(n in self.by_n for n in marks) else dropped).append(sent)
        return " ".join(kept), dropped

    def validate(self, text: str, quotes: list[tuple[int, str]] | None = None) -> Report:
        rep = Report(cleaned=text)
        # 1. markers must reference a shown passage
        def fix(m: re.Match) -> str:
            rep.total_citations += 1
            if int(m.group(1)) in self.by_n:
                rep.valid_citations += 1
                return m.group(0)
            rep.issues.append(f"removed citation [S{m.group(1)}]: no such retrieved source")
            return ""
        cleaned = _MARK.sub(fix, text)
        # 2. quotations must appear verbatim (after normalisation) in the cited passage
        for n, q in quotes or []:
            rep.total_citations += 1
            if self.quote_supported(n, q):
                rep.valid_citations += 1
            else:
                rep.issues.append(f"quotation attributed to [S{n}] not found in that passage")
                cleaned = cleaned.replace(q, "[unsupported quotation removed]")
        # 3. URLs must come from the retrieved sources' recorded URLs
        for u in set(_URL.findall(cleaned)):
            if u.rstrip(".,;") not in self.allowed_urls:
                rep.issues.append(f"removed URL not present in retrieved sources: {u}")
                cleaned = cleaned.replace(u, "[link removed]")
        # 4. statutory references asserted in generated prose must occur in the retrieved material
        for m in _SEC.finditer(cleaned):
            if _norm(f"section {m.group(1)}") not in self.corpus_norm and _norm(m.group(2)) not in self.corpus_norm:
                rep.issues.append(f"unsupported statutory reference: {m.group(0)}")
        rep.cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return rep
