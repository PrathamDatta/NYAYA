"""IndicTranslationService: English -> Indic translation with law-ai/InLegalTrans-En2Indic-1B.

Only the nine target languages listed on the model card are accepted. Output is machine translation and
must never be presented as the authoritative text of a statute or judgment (the API labels it accordingly).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import get_settings
from .registry import ModelSpec, ModelUnavailableError, manager, resolve_device

# Verified from the model card (language list) and FLORES-200 codes used by IndicTrans2.
SUPPORTED_TARGETS: dict[str, tuple[str, str]] = {
    "bn": ("ben_Beng", "Bengali"), "hi": ("hin_Deva", "Hindi"), "mr": ("mar_Deva", "Marathi"),
    "ta": ("tam_Taml", "Tamil"), "te": ("tel_Telu", "Telugu"), "ml": ("mal_Mlym", "Malayalam"),
    "pa": ("pan_Guru", "Punjabi"), "gu": ("guj_Gujr", "Gujarati"), "or": ("ory_Orya", "Odia"),
}
SRC_TAG = "eng_Latn"
MAX_TOKENS = 256
DISCLAIMER = ("Machine translation by InLegalTrans-En2Indic-1B for understanding only. "
              "It is not the authoritative legal text; rely on the official English/Hindi publication.")


class UnsupportedLanguageError(ValueError):
    pass


class DualSPTokenizer:
    """Minimal re-implementation of the IndicTrans2 tokenizer (separate SentencePiece models per side)."""

    def __init__(self, d: Path):
        import sentencepiece as spm

        self.sp_src = spm.SentencePieceProcessor(model_file=str(d / "model.SRC"))
        self.sp_tgt = spm.SentencePieceProcessor(model_file=str(d / "model.TGT"))
        self.enc = json.loads((d / "dict.SRC.json").read_text(encoding="utf-8"))
        self.dec_vocab = json.loads((d / "dict.TGT.json").read_text(encoding="utf-8"))
        self.id2tok = {v: k for k, v in self.dec_vocab.items()}
        self.bos, self.pad, self.eos, self.unk = (self.enc["<s>"], self.enc["<pad>"], self.enc["</s>"], self.enc["<unk>"])

    def encode(self, text: str, tgt_tag: str) -> list[int]:
        pieces = [SRC_TAG, tgt_tag, *self.sp_src.encode(text, out_type=str)]
        ids = [self.enc.get(p, self.unk) for p in pieces][: MAX_TOKENS - 1]
        return [*ids, self.eos]

    def decode(self, ids: list[int]) -> str:
        toks = [self.id2tok.get(i, "") for i in ids if i not in (self.bos, self.pad, self.eos)]
        return self.sp_tgt.decode_pieces(toks).strip()

    def token_len(self, text: str) -> int:
        return len(self.sp_src.encode(text, out_type=str)) + 3


@dataclass
class _TransBundle:
    tok: DualSPTokenizer
    model: Any
    device: str


def _load(spec: ModelSpec, path: Path) -> _TransBundle:
    import torch

    from .vendor.indictrans2.configuration_indictrans import IndicTransConfig
    from .vendor.indictrans2.modeling_indictrans import IndicTransForConditionalGeneration

    cfg = IndicTransConfig.from_pretrained(str(path), local_files_only=True)
    model = IndicTransForConditionalGeneration.from_pretrained(str(path), config=cfg, local_files_only=True,
                                                               low_cpu_mem_usage=True)
    device = resolve_device()
    if get_settings().translation_quantize_int8 and device == "cpu":
        model = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
    model.to(device).eval()
    return _TransBundle(DualSPTokenizer(path), model, device)


# IndicTrans2 decodes every Indic language in a unified Devanagari form; the official IndicProcessor then
# transliterates it into the target script. Unicode Indic blocks are laid out in parallel, so a block-offset
# mapping reproduces that step. Characters with no counterpart in the target block fall back as noted below.
_BLOCK = {"bn": 0x0980, "pa": 0x0A00, "gu": 0x0A80, "or": 0x0B00, "ta": 0x0B80, "te": 0x0C00, "ml": 0x0D00}
_TAMIL_FALLBACK = {"ख": "க", "ग": "க", "घ": "க", "छ": "ச", "झ": "ஜ", "ठ": "ட", "ड": "ட", "ढ": "ட",
                   "थ": "த", "ध": "த", "फ": "ப", "ब": "ப", "भ": "ப"}
_SENT_PUNCT = re.compile(r"\s+([,;:?!।.)\]])")
_OPEN_PUNCT = re.compile(r"([(\[])\s+")


def to_target_script(text: str, lang: str) -> str:
    import unicodedata

    base = _BLOCK.get(lang)
    if base is None:  # hi, mr stay in Devanagari
        return text
    out = []
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F and cp not in (0x0964, 0x0965):
            if lang == "ta" and ch in _TAMIL_FALLBACK:
                out.append(_TAMIL_FALLBACK[ch])
                continue
            mapped = chr(base + (cp - 0x0900))
            out.append(mapped if unicodedata.category(mapped) != "Cn" else ch)
        elif cp in (0x0964, 0x0965):
            out.append("." if lang in ("ta", "te", "ml") else "।")
        else:
            out.append(ch)
    res = "".join(out)
    for src, dst in _NUKTA.get(lang, ()):
        res = res.replace(src, dst)
    return res


# Devanagari consonant+nukta maps to consonant+nukta in other blocks; these scripts have precomposed letters.
_NUKTA = {
    "bn": (("\u09a1\u09bc", "\u09dc"), ("\u09a2\u09bc", "\u09dd"), ("\u09af\u09bc", "\u09df")),
    "or": (("\u0b21\u0b3c", "\u0b5c"), ("\u0b22\u0b3c", "\u0b5d"), ("\u0b2f\u0b3c", "\u0b5f")),
}


def detokenize(text: str) -> str:
    text = _SENT_PUNCT.sub(r"\1", text)
    return _OPEN_PUNCT.sub(r"\1", text)


_SENT = re.compile(r"(?<=[.;?!])\s+(?=[(\[A-Z0-9\"'])")


def split_sentences(text: str, tok: DualSPTokenizer | None = None) -> list[str]:
    parts: list[str] = []
    for para in re.split(r"\n\s*\n", text.strip()):
        for s in _SENT.split(para.strip()):
            s = re.sub(r"\s+", " ", s).strip()
            if s:
                parts.append(s)
    return parts


class IndicTranslationService:
    key = "inlegaltrans"

    @staticmethod
    def languages() -> dict[str, str]:
        return {code: name for code, (_, name) in SUPPORTED_TARGETS.items()}

    def _bundle(self) -> _TransBundle:
        return manager.get(self.key, _load)

    def translate(self, text: str, target: str, beams: int = 4) -> dict:
        import torch

        if target not in SUPPORTED_TARGETS:
            raise UnsupportedLanguageError(
                f"'{target}' is not supported. Supported: {', '.join(sorted(SUPPORTED_TARGETS))}")
        if not text.strip():
            raise ValueError("empty text")
        if len(text) > 8000:
            raise ValueError("text too long (max 8000 characters per request)")
        tag = SUPPORTED_TARGETS[target][0]
        b = self._bundle()
        sents = split_sentences(text)
        t0 = time.perf_counter()
        outs: list[str] = []
        for lo in range(0, len(sents), 4):
            batch = sents[lo:lo + 4]
            enc = [b.tok.encode(s, tag) for s in batch]
            width = max(len(e) for e in enc)
            ids = torch.full((len(enc), width), b.tok.pad, dtype=torch.long)
            mask = torch.zeros((len(enc), width), dtype=torch.long)
            for i, e in enumerate(enc):  # left-aligned, right padding
                ids[i, :len(e)] = torch.tensor(e)
                mask[i, :len(e)] = 1
            with torch.inference_mode():
                gen = b.model.generate(input_ids=ids.to(b.device), attention_mask=mask.to(b.device),
                                       num_beams=beams, num_return_sequences=1, max_length=MAX_TOKENS,
                                       do_sample=False, use_cache=True)
            outs.extend(b.tok.decode(g.tolist()) for g in gen)
        return {"target": target, "language": SUPPORTED_TARGETS[target][1], "translation": to_target_script(detokenize(" ".join(outs)), target),
                "sentences": len(sents), "seconds": round(time.perf_counter() - t0, 2), "disclaimer": DISCLAIMER,
                "model": "law-ai/InLegalTrans-En2Indic-1B"}


def require_available() -> None:
    from .registry import SPECS, is_downloaded

    if not is_downloaded(SPECS["inlegaltrans"]):
        raise ModelUnavailableError("inlegaltrans", "weights not downloaded; run `python -m app.cli download-models`")
