"""Pinned model specifications and a resource-aware model manager.

Weights are downloaded once by `python -m app.cli download-models` and then loaded from the local cache.
Nothing is fetched per request. When more models are requested than `max_loaded_models`, the least
recently used one is unloaded instead of failing or silently skipping an integration.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..config import get_settings

log = logging.getLogger("nyaya.ml")


class ModelUnavailableError(RuntimeError):
    """The model cannot be used (not downloaded, out of memory, dependency missing)."""

    def __init__(self, key: str, reason: str):
        super().__init__(f"Model '{key}' is unavailable: {reason}")
        self.key, self.reason = key, reason


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repo_id: str
    revision: str
    role: str
    kind: str  # encoder | translation | generator
    approx_disk_mb: int
    approx_ram_mb: int
    patterns: tuple[str, ...]


# Revisions were read from the Hugging Face API on 2026-10-28.
SPECS: dict[str, ModelSpec] = {
    "inlegalbert": ModelSpec(
        "inlegalbert", "law-ai/InLegalBERT", "b5ecfed8ed6cf9d25a3cb8225a8c52f161f7401a",
        "Statute / provision passage representation (LegalTextEncoder)", "encoder", 440, 700,
        ("*.json", "*.txt", "pytorch_model.bin"),
    ),
    "incaselawbert": ModelSpec(
        "incaselawbert", "law-ai/InCaseLawBERT", "7f2c2a0c1ff4149e8c4a8c79ee9f24757ad5dacd",
        "Judgment / case-law passage representation (CaseLawEncoder)", "encoder", 440, 700,
        ("*.json", "*.txt", "pytorch_model.bin"),
    ),
    "custominlawbert": ModelSpec(
        "custominlawbert", "law-ai/CustomInLawBERT", "47a0ba28e05bda6b92522de1a70677181706d12b",
        "Legal-topic identification and complementary representation (CustomLegalNLP)", "encoder", 440, 700,
        ("*.json", "*.txt", "pytorch_model.bin"),
    ),
    "inlegaltrans": ModelSpec(
        "inlegaltrans", "law-ai/InLegalTrans-En2Indic-1B", "6413ed9b8d944ce067cdfa24a81f5d022155f683",
        "English to Indic legal translation (IndicTranslationService)", "translation", 4400, 5200,
        ("*.json", "model.safetensors", "*.SRC", "*.TGT"),
    ),
}


def _llm_spec() -> ModelSpec:
    s = get_settings()
    return ModelSpec("local_llm", s.local_llm_repo, s.local_llm_revision or "main",
                     "Optional local text generator for grounded answers (LegalAnswerGenerator)", "generator", 3100, 6500,
                     ("*.json", "*.safetensors", "*.txt", "merges.txt"))


def get_spec(key: str) -> ModelSpec:
    return _llm_spec() if key == "local_llm" else SPECS[key]


def snapshot_dir(spec: ModelSpec) -> Path | None:
    """Locate the pinned snapshot inside the local cache without touching the network."""
    base = get_settings().models_path / ("models--" + spec.repo_id.replace("/", "--")) / "snapshots"
    if spec.revision == "main":  # unpinned (only the optional LLM when no revision is configured)
        found = sorted(base.glob("*")) if base.is_dir() else []
        return found[-1] if found else None
    root = base / spec.revision
    return root if root.is_dir() else None


def is_downloaded(spec: ModelSpec) -> bool:
    d = snapshot_dir(spec)
    if d is None:
        return False
    if spec.kind == "translation":
        return (d / "model.safetensors").exists() and (d / "model.SRC").exists()
    if spec.kind == "generator":
        return (d / "config.json").exists() and any(d.glob("*.safetensors"))
    return (d / "pytorch_model.bin").exists() and (d / "config.json").exists()


def download(spec: ModelSpec) -> Path:
    from huggingface_hub import snapshot_download

    s = get_settings()
    return Path(snapshot_download(spec.repo_id, revision=spec.revision, cache_dir=str(s.models_path),
                                  allow_patterns=list(spec.patterns), token=s.hf_token))


def resolve_device() -> str:
    d = get_settings().device
    if d == "auto":
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    return d


class ModelManager:
    """Thread-safe lazy loader with LRU unloading."""

    def __init__(self) -> None:
        self._loaded: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()
        self.load_seconds: dict[str, float] = {}

    def get(self, key: str, loader: Callable[[ModelSpec, Path], Any]) -> Any:
        spec = get_spec(key)
        with self._lock:
            if key in self._loaded:
                self._loaded.move_to_end(key)
                return self._loaded[key]
            if not is_downloaded(spec):
                raise ModelUnavailableError(key, f"weights for {spec.repo_id}@{spec.revision[:8]} are not downloaded; "
                                                 "run `python -m app.cli download-models`")
            st = get_settings()
            budget = st.memory_budget_mb
            if spec.approx_ram_mb > budget:
                raise ModelUnavailableError(key, f"needs about {spec.approx_ram_mb} MB RAM but NYAYA_MEMORY_BUDGET_MB is {budget}")

            def used() -> int:
                return sum(get_spec(k).approx_ram_mb for k in self._loaded)

            while self._loaded and (used() + spec.approx_ram_mb > budget or len(self._loaded) >= max(1, st.max_loaded_models)):
                old, _ = self._loaded.popitem(last=False)  # least recently used first
                log.info("unloading model %s to fit %s within %d MB budget", old, key, budget)
                self._free()
            t0 = time.perf_counter()
            try:
                obj = loader(spec, snapshot_dir(spec))  # type: ignore[arg-type]
            except ModelUnavailableError:
                raise
            except MemoryError as e:
                raise ModelUnavailableError(key, "out of memory while loading") from e
            except Exception as e:  # noqa: BLE001 - surfaced as a typed, user-visible error
                log.exception("failed loading %s", key)
                raise ModelUnavailableError(key, f"{type(e).__name__}: {e}") from e
            self.load_seconds[key] = round(time.perf_counter() - t0, 2)
            self._loaded[key] = obj
            return obj

    def unload(self, key: str) -> None:
        with self._lock:
            self._loaded.pop(key, None)
            self._free()

    def loaded_keys(self) -> list[str]:
        with self._lock:
            return list(self._loaded)

    @staticmethod
    def _free() -> None:
        import gc

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass


manager = ModelManager()


def status() -> list[dict[str, Any]]:
    out = []
    s0 = get_settings()
    specs = list(SPECS.values()) + ([_llm_spec()] if s0.generator_backend == "local_llm" else [])
    for s in specs:
        out.append({
            "key": s.key, "repo_id": s.repo_id, "revision": s.revision, "role": s.role, "kind": s.kind,
            "downloaded": is_downloaded(s), "loaded": s.key in manager.loaded_keys(),
            "approx_disk_mb": s.approx_disk_mb, "approx_ram_mb": s.approx_ram_mb,
        })
    return out
