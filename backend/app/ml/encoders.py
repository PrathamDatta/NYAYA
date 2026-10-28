"""Encoder services built on the three Law-AI BERT checkpoints.

The checkpoints are masked-language-model encoders (no sentence-embedding head). We therefore use
attention-masked mean pooling over the last hidden layer, window long passages to the 512-token limit,
L2-normalise, and (optionally) centre vectors with corpus statistics to reduce BERT anisotropy.
Whether this yields useful retrieval is measured by `eval/run_eval.py`, not assumed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

import numpy as np

from ..config import get_settings
from .registry import SPECS, ModelSpec, manager, resolve_device


class _Bundle:
    def __init__(self, tokenizer, model, device: str):  # noqa: ANN001
        self.tokenizer, self.model, self.device = tokenizer, model, device


def _load_bert(spec: ModelSpec, path: Path) -> _Bundle:
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(path), local_files_only=True, model_max_length=512)
    model = AutoModel.from_pretrained(str(path), local_files_only=True, add_pooling_layer=False)
    device = resolve_device()
    model.to(device).eval()
    torch.set_grad_enabled(False)
    return _Bundle(tok, model, device)


class BertEncoder:
    """Base class: lazy-loaded, windowed mean-pooling encoder."""

    key: str = ""

    def __init__(self) -> None:
        self.spec = SPECS[self.key]

    @property
    def revision(self) -> str:
        return self.spec.revision

    def _bundle(self) -> _Bundle:
        return manager.get(self.key, _load_bert)

    def encode(self, texts: Sequence[str], batch_size: int | None = None) -> np.ndarray:
        """Return an (n, 768) float32 matrix of L2-normalised vectors."""
        import torch

        s = get_settings()
        b = self._bundle()
        max_len = min(s.max_seq_len, 512)
        bs = batch_size or s.encode_batch_size
        # Window each text into <= max_len-token pieces; the text vector is the mean of its window vectors.
        windows: list[list[int]] = []
        owner: list[int] = []
        for i, t in enumerate(texts):
            ids = b.tokenizer(t or " ", add_special_tokens=False, truncation=False)["input_ids"]
            step = max_len - 2
            for start in range(0, max(len(ids), 1), step):
                windows.append(ids[start:start + step])
                owner.append(i)
                if len(windows) > 20000:
                    raise ValueError("text too long")
        order = sorted(range(len(windows)), key=lambda k: len(windows[k]))
        out = np.zeros((len(windows), b.model.config.hidden_size), dtype=np.float32)
        for lo in range(0, len(order), bs):
            idx = order[lo:lo + bs]
            batch = [[b.tokenizer.cls_token_id, *windows[k], b.tokenizer.sep_token_id] for k in idx]
            width = max(len(x) for x in batch)
            ids_t = torch.full((len(batch), width), b.tokenizer.pad_token_id, dtype=torch.long)
            mask = torch.zeros((len(batch), width), dtype=torch.long)
            for r, x in enumerate(batch):
                ids_t[r, :len(x)] = torch.tensor(x)
                mask[r, :len(x)] = 1
            with torch.inference_mode():
                h = b.model(input_ids=ids_t.to(b.device), attention_mask=mask.to(b.device)).last_hidden_state
            m = mask.to(b.device).unsqueeze(-1).to(h.dtype)
            pooled = ((h * m).sum(1) / m.sum(1).clamp(min=1)).float().cpu().numpy()
            for r, k in enumerate(idx):
                out[k] = pooled[r]
        res = np.zeros((len(texts), out.shape[1]), dtype=np.float32)
        counts = np.zeros(len(texts), dtype=np.float32)
        for k, i in enumerate(owner):
            res[i] += out[k]
            counts[i] += 1
        res /= np.maximum(counts, 1)[:, None]
        return res  # raw (un-normalised) mean vectors; see normalise()/center()

    @staticmethod
    def normalise(x: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(x, axis=1, keepdims=True)
        return (x / np.maximum(n, 1e-9)).astype(np.float32)

    @staticmethod
    def center(x: np.ndarray, mean: np.ndarray | None) -> np.ndarray:
        return x if mean is None else x - mean

    def embed(self, texts: Sequence[str], mean: np.ndarray | None = None) -> np.ndarray:
        return self.normalise(self.center(self.encode(texts), mean))


class LegalTextEncoder(BertEncoder):
    """InLegalBERT: statute / provision passages and queries about them."""
    key = "inlegalbert"


class CaseLawEncoder(BertEncoder):
    """InCaseLawBERT: judgment passages and case-matching queries."""
    key = "incaselawbert"


class CustomLegalNLP(BertEncoder):
    """CustomInLawBERT (own domain-specific WordPiece vocabulary).

    Role: legal-topic identification by nearest topic prototype, plus a third representation
    that is only kept in retrieval fusion if evaluation shows a measurable gain.
    """
    key = "custominlawbert"

    def __init__(self) -> None:
        super().__init__()
        self._protos: tuple[list[str], np.ndarray] | None = None

    def classify_topic(self, text: str, topics: dict[str, str]) -> list[tuple[str, float]]:
        """Rank topics by cosine similarity to prototype descriptions. Returns [(topic, score)] best first."""
        if self._protos is None or self._protos[0] != list(topics):
            names = list(topics)
            self._protos = (names, self.embed([topics[n] for n in names]))
        q = self.embed([text])[0]
        sims = self._protos[1] @ q
        order = np.argsort(-sims)
        return [(self._protos[0][i], float(sims[i])) for i in order]


_WS = re.compile(r"\s+")


def clean_for_encoding(text: str) -> str:
    return _WS.sub(" ", text).strip()
