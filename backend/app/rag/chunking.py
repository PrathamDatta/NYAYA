"""Chunking that preserves legal structure (sections / numbered paragraphs) and page references."""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_WORDS = 300
MIN_WORDS = 40


@dataclass
class ChunkDraft:
    ref_label: str
    page_start: int | None
    page_end: int | None
    text: str


_SECTION = re.compile(r"(?m)^\s*(\d{1,3}[A-Z]{0,2})\.\s+([A-Z][^\n]{2,140}?)(?:\.[—\-–]|\.\s*$|[—–]\s)")
_PARA = re.compile(r"(?m)^\s*(\d{1,3})\.\s+(?=[A-Z\"'(])")
_SENT = re.compile(r"(?<=[.;?!])\s+(?=[A-Z(\"'0-9])")

_HEADER_JUNK = re.compile(r"(?im)^\s*(?:[A-H]|\d{1,4}|supreme\s+court\s+reports|\[\d{4}\]\s*\d+\s*s\.c\.r\.|digital\s+supreme\s+court\s+reports)\s*$")


def clean_report_text(page_text: str) -> str:
    """Remove margin letters, bare page numbers and running headers found in law-report PDFs."""
    t = _HEADER_JUNK.sub("", page_text)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _page_of(offsets: list[int], pos: int) -> int:
    lo = 0
    for i, o in enumerate(offsets):
        if o <= pos:
            lo = i
        else:
            break
    return lo + 1


def _split_long(label: str, text: str, p0: int | None, p1: int | None) -> list[ChunkDraft]:
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [ChunkDraft(label, p0, p1, text.strip())]
    sents = _SENT.split(text)
    out: list[ChunkDraft] = []
    cur: list[str] = []
    n = 0
    for s in sents:
        w = len(s.split())
        if cur and n + w > MAX_WORDS:
            out.append(ChunkDraft(label if not out else f"{label} (cont.)", p0, p1, " ".join(cur)))
            cur, n = [], 0
        cur.append(s)
        n += w
    if cur:
        out.append(ChunkDraft(label if not out else f"{label} (cont.)", p0, p1, " ".join(cur)))
    return out


def chunk_document(pages: list[str], doc_type: str) -> list[ChunkDraft]:
    """Split a document given per-page text. `doc_type` selects statute (sections) vs judgment (paragraphs)."""
    full, offsets = "", []
    for p in pages:
        offsets.append(len(full))
        full += p + "\n\n"
    if not full.strip():
        return []
    pattern = _SECTION if doc_type in ("statute", "rule", "synthetic") else _PARA
    marks = [(m.start(), m.group(1), (m.group(2).strip() if pattern is _SECTION else "")) for m in pattern.finditer(full)]
    # keep monotonically increasing section/paragraph numbers to ignore list items and stray numerals
    seq: list[tuple[int, str, str]] = []
    last = 0
    for pos, num, title in marks:
        digits = int(re.match(r"\d+", num).group())  # type: ignore[union-attr]
        if digits >= last and digits - last <= 12:
            seq.append((pos, num, title))
            last = digits
    drafts: list[ChunkDraft] = []
    if len(seq) >= 3:
        pre = full[: seq[0][0]].strip()
        if len(pre.split()) >= MIN_WORDS:
            drafts += _split_long("Preamble / headnote", pre, 1, _page_of(offsets, seq[0][0]))
        for i, (pos, num, title) in enumerate(seq):
            end = seq[i + 1][0] if i + 1 < len(seq) else len(full)
            body = full[pos:end].strip()
            label = (f"Section {num}" + (f" — {title}" if title else "")) if pattern is _SECTION else f"Paragraph {num}"
            drafts += _split_long(label, re.sub(r"\s+", " ", body), _page_of(offsets, pos), _page_of(offsets, max(pos, end - 1)))
    else:  # fallback: paragraph windows
        paras = [p for p in re.split(r"\n\s*\n", full) if p.strip()]
        buf, start = [], 0
        pos = 0
        for p in paras:
            buf.append(p.strip())
            if sum(len(x.split()) for x in buf) >= 200:
                txt = re.sub(r"\s+", " ", " ".join(buf))
                drafts += _split_long(f"Passage {len(drafts) + 1}", txt, _page_of(offsets, start), _page_of(offsets, min(pos, len(full) - 1)))
                buf, start = [], pos
            pos += len(p) + 2
        if buf:
            txt = re.sub(r"\s+", " ", " ".join(buf))
            drafts += _split_long(f"Passage {len(drafts) + 1}", txt, _page_of(offsets, start), len(pages))
    if doc_type in ("statute", "rule", "synthetic"):
        # Every section is its own citable unit; never merge across section boundaries.
        return [d for d in drafts if d.text.strip()]
    merged: list[ChunkDraft] = []
    carry: ChunkDraft | None = None
    for d in drafts:
        if carry is not None:  # fold a tiny paragraph into the next one, with an honest range label
            a, b = carry.ref_label.replace("Paragraph ", ""), d.ref_label.replace("Paragraph ", "")
            if d.ref_label.startswith("Paragraph") and carry.ref_label.startswith("Paragraph") and "(cont.)" not in b:
                d = ChunkDraft(f"Paragraphs {a.split('–')[0]}–{b.split('–')[-1]}", carry.page_start, d.page_end, carry.text + " " + d.text)
            else:
                merged.append(carry)
            carry = None
        if len(d.text.split()) < MIN_WORDS and not d.ref_label.endswith("(cont.)") and d.ref_label.startswith("Paragraph"):
            carry = d
        else:
            merged.append(d)
    if carry is not None:
        merged.append(carry)
    return [d for d in merged if d.text.strip()]
