from __future__ import annotations

import math
import re
from collections import Counter

STOP = frozenset("""a an the of to in on at by for with and or nor but if then than that this these those is are was were be been being
it its as from into under over upon such any all shall may can could would should will not no which who whom whose what when where
there their his her he she they them we you your our i me my also other any one two per etc said explain tell please does do did have has had about whether""".split())

_TOK = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


_SUFFIXES = ("ations", "ation", "ings", "ing", "edly", "ied", "ies", "ers", "ery", "er", "ed", "es", "s", "ly")


def stem(w: str) -> str:
    """Tiny suffix stripper so robbed / robbery / robbing / robber all match. Applied identically to documents and queries."""
    if len(w) <= 3 or not w.isalpha():
        return w
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)] + ("y" if suf in ("ied", "ies") else "")
            break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiou":  # robb -> rob
        w = w[:-1]
    return w


def tokens(text: str) -> list[str]:
    return [stem(t) for t in _TOK.findall(text.lower()) if t not in STOP and len(t) > 1]


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.len = [len(d) for d in docs]
        self.avg = (sum(self.len) / self.n) if self.n else 0.0
        self.tf: list[Counter] = [Counter(d) for d in docs]
        df: Counter = Counter()
        for c in self.tf:
            df.update(c.keys())
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.inv: dict[str, list[int]] = {}
        for i, c in enumerate(self.tf):
            for t in c:
                self.inv.setdefault(t, []).append(i)

    def scores(self, query: list[str]) -> dict[int, float]:
        out: dict[int, float] = {}
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.inv[t]:
                f = self.tf[i][t]
                denom = f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1))
                out[i] = out.get(i, 0.0) + idf * f * (self.k1 + 1) / denom
        return out
