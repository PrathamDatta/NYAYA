# The four Law-AI models

Verified against the Hugging Face API and model cards on 2026-10-28. All four are MIT-licensed, ungated and published by
Law-AI (IIT Kharagpur). Revisions are pinned in `backend/app/ml/registry.py`; weights are downloaded once by
`python -m app.cli download-models` and loaded with `local_files_only` — nothing is fetched per request.

| Key | Repository | Pinned revision | Architecture / files | Disk | Role in this system |
|---|---|---|---|---|---|
| `inlegalbert` | `law-ai/InLegalBERT` | `b5ecfed8ed6cf9d25a3cb8225a8c52f161f7401a` | BERT-base (12L, 768d, ~110M), initialised from LEGAL-BERT-SC, +300K MLM/NSP steps on ~5.4M Indian court documents; `BertForPreTraining`, 512 tokens, custom legal vocabulary | ~440 MB | `LegalTextEncoder`: passage/query representation for retrieval |
| `incaselawbert` | `law-ai/InCaseLawBERT` | `7f2c2a0c1ff4149e8c4a8c79ee9f24757ad5dacd` | Same configuration, initialised from CaseLawBERT (zlucia), same corpus; 512 tokens | ~440 MB | `CaseLawEncoder`: judgment-passage representation |
| `custominlawbert` | `law-ai/CustomInLawBERT` | `47a0ba28e05bda6b92522de1a70677181706d12b` | BERT-base `BertForMaskedLM`; **custom WordPiece vocabulary trained on Indian legal text** (the card's usage snippet pairs this tokenizer with InLegalBERT weights; we use tokenizer and weights from this repository together) | ~440 MB | `CustomLegalNLP`: legal-topic identification (prototype similarity) |
| `inlegaltrans` | `law-ai/InLegalTrans-En2Indic-1B` | `6413ed9b8d944ce067cdfa24a81f5d022155f683` | IndicTrans2 1.12B seq2seq (18+18 layers, d=1024), fine-tuned on MILPaC; fp32 safetensors; max 256 tokens | ~4.5 GB | `IndicTranslationService`: English→Indic translation |

## What these models can and cannot do

* The three BERTs are **masked-language-model encoders**. They have no sentence-embedding head and cannot generate answers. We mean-pool the last hidden layer (attention-masked), window texts longer than 512 tokens, L2-normalise, and centre with corpus statistics. Raw cosine similarities from these encoders are tightly clustered (e.g. 0.77–0.81 between unrelated legal sentences in a smoke test), so retrieval always fuses them with BM25 and their value is **measured**, not assumed — see `docs/EVALUATION.md`.
* The translator supports **exactly** these targets (from the model card): Bengali `bn`, Hindi `hi`, Marathi `mr`, Tamil `ta`, Telugu `te`, Malayalam `ml`, Punjabi `pa`, Gujarati `gu`, Odia `or` (FLORES codes `ben_Beng hin_Deva mar_Deva tam_Taml tel_Telu mal_Mlym pan_Guru guj_Gujr ory_Orya`). Source is English only. Any other language is refused with HTTP 422. The card's own scores are lowest for Odia (BLEU 14.2).
* IndicTrans2 decodes all Indic languages in a unified Devanagari form; `app/ml/translation.py` converts it to the target script (Unicode block offset mapping with documented fallbacks) and detokenises punctuation, reproducing what `IndicProcessor.postprocess` does.
* Decoding uses deterministic beam search (4 beams). The model card's example passes `do_sample=True` together with beams, which makes output non-reproducible; we deliberately do not.
* Machine translation is labelled in the API and UI and is never presented as authoritative text.

## Why IndicTrans2 code is vendored

`InLegalTrans`' `config.json` points to modelling code in the **gated** `ai4bharat/indictrans2-en-indic-1B` repository and needs `trust_remote_code=True`. We instead vendor the unmodified Apache-2.0 files from AI4Bharat's GitHub (`app/ml/vendor/indictrans2/`, hashes in its README) and wrote a small tokenizer, so there is no remote code execution, no HF login, and no `IndicTransToolkit` (a C-extension build that is awkward on Windows). Verified: real weights load, and translation into all nine languages produces output in the correct script.

## Text generation

The four models do not write answers. The default `extractive` generator quotes retrieved passages. An optional `local_llm` backend (`NYAYA_GENERATOR_BACKEND=local_llm`, default repo `Qwen/Qwen2.5-1.5B-Instruct`, **you must pin a revision**) can write a plain-language summary under a "use only the sources" prompt, followed by citation validation. It is optional because on CPU it is slow and a small model can still misparaphrase; no external paid API is ever used. Status: implemented, **not** exercised in this build's test run (see Known limitations).

## Memory behaviour

Models load lazily and the least-recently-used are unloaded to stay under `NYAYA_MEMORY_BUDGET_MB` (default 8000). A model larger than the budget is refused with a clear error rather than risking an out-of-memory crash. Concurrent inference is capped (2) with HTTP 503 "busy" beyond it.
