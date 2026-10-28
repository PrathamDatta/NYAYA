"""Thin helper so ingestion embeds with exactly the same pooling/normalisation as query time (uncentred, L2-normalised)."""
from __future__ import annotations

import numpy as np

from ..ml.encoders import BertEncoder, CaseLawEncoder, CustomLegalNLP, LegalTextEncoder, clean_for_encoding

_ENC: dict[str, BertEncoder] = {}


def encoder(key: str) -> BertEncoder:
    if key not in _ENC:
        _ENC[key] = {"inlegalbert": LegalTextEncoder, "incaselawbert": CaseLawEncoder, "custominlawbert": CustomLegalNLP}[key]()
    return _ENC[key]


def embed_texts(key: str, texts: list[str]) -> np.ndarray:
    return BertEncoder.normalise(encoder(key).encode([clean_for_encoding(t) for t in texts]))
