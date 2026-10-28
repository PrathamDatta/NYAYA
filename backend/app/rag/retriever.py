"""LegalRetriever: query normalisation, hybrid retrieval (BM25 + dense), metadata/temporal filtering, RRF ranking."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Sequence

import numpy as np
from sqlalchemy.orm import Session

from ..config import get_settings
from ..ml.registry import ModelUnavailableError
from .index import Hit, get_index, source_validity
from .rag_models import embed_texts
from .textutil import tokens

# Lay-to-legal vocabulary expansion. This is query *rewriting for lexical matching only*, not legal advice.
SYNONYMS = {
    "landlord": ["lessor"], "tenant": ["lessee"], "rent": ["lease", "tenancy"], "deposit": ["security deposit"],
    "cheated": ["cheating", "deception", "fraud"], "scam": ["cheating", "fraud"], "fraud": ["cheating"],
    "refund": ["consideration", "price"], "defective": ["defect", "deficiency"], "fir": ["first information report"],
    "police": ["investigation"], "salary": ["wages"], "sacked": ["termination", "dismissal"], "fired": ["termination"],
    "bribe": ["illegal gratification"], "divorce": ["dissolution of marriage", "matrimonial"],
    "husband": ["spouse"], "wife": ["spouse"], "court": ["tribunal"], "notice": ["legal notice"],
}
_ABBREV = {"ipc": "indian penal code", "bns": "bharatiya nyaya sanhita", "bnss": "bharatiya nagarik suraksha sanhita",
           "bsa": "bharatiya sakshya adhiniyam", "cpc": "code of civil procedure", "crpc": "code of criminal procedure",
           "cpa": "consumer protection act", "tpa": "transfer of property act", "it act": "information technology act"}


def normalise_query(q: str) -> tuple[str, list[str]]:
    """Return (cleaned query, extra lexical expansion terms)."""
    q = re.sub(r"\s+", " ", q).strip()
    low = q.lower()
    extra: list[str] = []
    for lay, legal in SYNONYMS.items():
        if re.search(rf"\b{re.escape(lay)}\b", low):
            extra += legal
    for ab, full in _ABBREV.items():
        if re.search(rf"\b{re.escape(ab)}\b", low):
            extra.append(full)
    return q, extra


@dataclass
class Filters:
    doc_types: Sequence[str] | None = None
    jurisdiction: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    as_of: date | None = None
    include_historical: bool = False
    include_synthetic: bool | None = None


class LegalRetriever:
    def __init__(self, components: Sequence[str] | None = None, pool: int = 60, rrf_k: int = 60):
        self.components = list(components) if components else None
        self.pool, self.rrf_k = pool, rrf_k

    def default_components(self) -> list[str]:
        return get_settings_components()

    def search(self, db: Session, query: str, filters: Filters | None = None, top_k: int | None = None,
               components: Sequence[str] | None = None) -> tuple[list[Hit], dict]:
        s = get_settings()
        filters = filters or Filters()
        top_k = top_k or s.retrieval_top_k
        comps = list(components or self.components or self.default_components())
        idx = get_index(db)
        info: dict = {"components": comps, "corpus_chunks": len(idx.chunk_ids), "skipped": {}}
        if not idx.chunk_ids:
            return [], info
        q, extra = normalise_query(query)
        info["expansion"] = extra
        as_of = filters.as_of or date.today()

        allowed = np.ones(len(idx.chunk_ids), dtype=bool)
        warn: dict[int, str | None] = {}
        for i, m in enumerate(idx.meta):
            src = idx.sources[m["source_id"]]
            if src["is_synthetic"] and not (filters.include_synthetic if filters.include_synthetic is not None else s.include_synthetic_corpus):
                allowed[i] = False
                continue
            if filters.doc_types and src["doc_type"] not in filters.doc_types:
                allowed[i] = False
                continue
            if filters.jurisdiction and src["jurisdiction"].lower() != filters.jurisdiction.lower():
                allowed[i] = False
                continue
            y = (src["publication_date"] or src["effective_from"])
            if y and ((filters.year_from and y.year < filters.year_from) or (filters.year_to and y.year > filters.year_to)):
                allowed[i] = False
                continue
            ok, w = source_validity(src, as_of, filters.include_historical)
            if not ok:
                allowed[i] = False
                info.setdefault("excluded_by_validity", {})[src["title"]] = w
                continue
            warn[i] = w

        rankings: dict[str, list[int]] = {}
        raw: dict[str, dict[int, float]] = {}
        if "bm25" in comps and idx.bm25:
            sc = idx.bm25.scores(tokens(q) + tokens(" ".join(extra)))
            order = sorted((i for i in sc if allowed[i]), key=lambda i: -sc[i])[: self.pool]
            rankings["bm25"], raw["bm25"] = order, {i: sc[i] for i in order}
        for key in (c for c in comps if c != "bm25"):
            try:
                qv = embed_texts(key, [q])[0]  # same pooling/normalisation as the stored vectors
            except ModelUnavailableError as e:
                info["skipped"][key] = e.reason
                continue
            ds = idx.dense_scores(key, qv)
            if ds is None:
                info["skipped"][key] = "no embeddings indexed for this model"
                continue
            ds = np.where(allowed, ds, -2.0)
            top = np.argsort(-ds)[: self.pool]
            rankings[key] = [int(i) for i in top if allowed[i]]
            raw[key] = {int(i): float(ds[i]) for i in rankings[key]}
        if not rankings:
            return [], info

        fused: dict[int, float] = {}
        ranks: dict[int, dict[str, int]] = {}
        for comp, order in rankings.items():
            for r, i in enumerate(order, start=1):
                fused[i] = fused.get(i, 0.0) + 1.0 / (self.rrf_k + r)
                ranks.setdefault(i, {})[comp] = r
        best = sorted(fused, key=lambda i: -fused[i])[:top_k]
        hits = []
        for i in best:
            m = idx.meta[i]
            h = Hit(idx.chunk_ids[i], m["source_id"], fused[i], m["text"], m["ref_label"], m["page_start"], m["page_end"],
                    _public_source(idx.sources[m["source_id"]]), ranks[i], {c: raw[c][i] for c in raw if i in raw[c]})
            if warn.get(i):
                h.warnings.append(warn[i])  # type: ignore[arg-type]
            hits.append(h)
        info["bm25_hits"] = len(rankings.get("bm25", []))
        cov_best, cov_union = query_coverage(idx.bm25, tokens(q), hits)
        info["coverage"], info["coverage_union"] = round(cov_best, 4), round(cov_union, 4)
        return hits, info


def _public_source(src: dict) -> dict:
    out = dict(src)
    for k in ("publication_date", "effective_from", "effective_to"):
        out[k] = out[k].isoformat() if out[k] else None
    return out


def get_settings_components() -> list[str]:
    from .. import runtime

    return runtime.RETRIEVAL_COMPONENTS


def query_coverage(bm25, q_terms: list[str], hits) -> tuple[float, float]:  # noqa: ANN001
    """IDF-weighted share of the question's content terms found in the retrieved passages.

    Returns (best_single_passage, union_of_passages). The *best single passage* is the gate: it requires the question's terms to
    co-occur in one passage, which separated answerable from unrelated questions better than the union (docs/EVALUATION.md).
    Terms the corpus has never seen count against coverage at the maximum IDF, so "cryptocurrency mining on the moon" fails
    even if a few common words occur somewhere."""
    terms = set(q_terms)
    if not terms or bm25 is None:
        return 0.0, 0.0
    max_idf = max(bm25.idf.values(), default=1.0)
    total = sum(bm25.idf.get(t, max_idf) for t in terms)
    per_hit = [terms & set(tokens(h.text)) for h in hits]
    weight = lambda present: sum(bm25.idf.get(t, max_idf) for t in present) / total  # noqa: E731
    best = max((weight(p) for p in per_hit), default=0.0)
    union = weight(set().union(*per_hit)) if per_hit else 0.0
    return best, union
