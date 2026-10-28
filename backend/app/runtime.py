"""Runtime choices that evaluation (eval/run_eval.py) is allowed to change. Defaults are set from measured results,
see docs/EVALUATION.md (InLegalBERT was the best encoder; InCaseLawBERT/CustomInLawBERT fusion did not help). Overridable with NYAYA_RETRIEVAL_COMPONENTS=bm25,inlegalbert,..."""
import os

RETRIEVAL_COMPONENTS: list[str] = [c for c in os.environ.get("NYAYA_RETRIEVAL_COMPONENTS", "bm25,inlegalbert").split(",") if c]
