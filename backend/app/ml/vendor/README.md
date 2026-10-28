# Vendored: IndicTrans2 modelling code

`indictrans2/configuration_indictrans.py` and `indictrans2/modeling_indictrans.py` are copied unmodified from
https://github.com/AI4Bharat/IndicTrans2 (`huggingface_interface/`, Apache-2.0, (c) The IndicTrans2 Authors and AI4Bharat).

Why vendored: `law-ai/InLegalTrans-En2Indic-1B` declares `auto_map` entries pointing at the *gated* repository
`ai4bharat/indictrans2-en-indic-1B`, which requires a Hugging Face login and `trust_remote_code=True`.
Vendoring removes runtime remote-code execution and the gated-repo dependency. Integrity hashes:

| file | sha256 |
|---|---|
| configuration_indictrans.py | d7e4ce84efacc18981228f5071b00dba6e3bf165f8ea7bcc8ecdada8942e1a52 |
| modeling_indictrans.py | 77cc301b892c379cfd17e029d28c919f5193740b5da3fc33c8ec53fb410e138b |

`app/ml/translation.py` implements its own SentencePiece dual-vocabulary tokenizer from the repository's
`model.SRC/model.TGT/dict.SRC.json/dict.TGT.json`, so the `IndicTransToolkit` (a C-extension build that is hard on Windows) is not needed.
