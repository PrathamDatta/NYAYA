import pytest

from app.ml import registry
from app.ml.translation import IndicTranslationService, UnsupportedLanguageError, split_sentences, to_target_script


@pytest.fixture()
def no_models(monkeypatch, tmp_path):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "model_dir", tmp_path)
    registry.manager._loaded.clear()


def test_missing_weights_raise_typed_error_not_fake_output(no_models):
    with pytest.raises(registry.ModelUnavailableError) as e:
        IndicTranslationService().translate("The tenant shall return the deposit.", "hi")
    assert "download-models" in str(e.value) and e.value.key == "inlegaltrans"


def test_translate_endpoint_returns_503_when_unavailable(client, user, no_models):
    r = client.post("/api/translate", json={"text": "Hello there", "target": "hi"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "model_unavailable"


def test_unsupported_language_is_refused(client, user):
    r = client.post("/api/translate", json={"text": "Hello", "target": "ur"})
    assert r.status_code == 422 and "Supported" in r.json()["error"]["message"]
    with pytest.raises(UnsupportedLanguageError):
        IndicTranslationService().translate("x y", "kn")


def test_pipeline_continues_without_dense_models(client, user, no_models, monkeypatch):
    """Dense encoders missing -> lexical retrieval still works and the response says which models were skipped."""
    from app import runtime

    monkeypatch.setattr(runtime, "RETRIEVAL_COMPONENTS", ["bm25", "inlegalbert"])
    r = client.post("/api/ask", json={"question": "refund of price for defective goods by seller"}).json()
    assert r["status"] == "ok" and "inlegalbert" in r["retrieval"]["skipped"]
    assert r["topic"].get("model_error")  # CustomInLawBERT unavailable: reported, not faked
    assert not any(m["model"].endswith("InLegalBERT") for m in r["models_used"])


def test_sentence_split_and_script_mapping():
    assert len(split_sentences("The seller shall refund. The buyer may complain; (a) in writing.")) >= 2
    assert to_target_script("किराया", "hi") == "किराया"
    assert to_target_script("कर।", "ta").endswith(".")
    assert all("஀" <= ch <= "௿" or ch == "." for ch in to_target_script("तिरुप", "ta"))


def test_supported_languages_match_model_card():
    assert set(IndicTranslationService.languages()) == {"bn", "hi", "mr", "ta", "te", "ml", "pa", "gu", "or"}
