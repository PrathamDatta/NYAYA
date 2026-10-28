from datetime import date

from app.rag.chunking import chunk_document
from app.rag.citations import CitationValidator
from app.rag.index import source_validity
from app.rag.textutil import BM25, tokens

from .conftest import SYNTH_ACT


def test_statute_chunking_preserves_sections_and_pages():
    ch = chunk_document([SYNTH_ACT[:600], SYNTH_ACT[600:]], "statute")
    labels = [c.ref_label for c in ch]
    assert any(l.startswith("Section 3") for l in labels) and any(l.startswith("Section 5") for l in labels)
    s3 = next(c for c in ch if c.ref_label.startswith("Section 3"))
    assert "refund of the price" in s3.text and s3.page_start in (1, 2)


def test_judgment_chunking_by_numbered_paragraph():
    text = "Preamble " + "word " * 60 + "\n\n" + "\n\n".join(f"{i}. The court considered point {i}. " + "reasoning " * 50 for i in range(1, 6))
    ch = chunk_document([text], "judgment")
    assert [c.ref_label for c in ch if c.ref_label.startswith("Paragraph")] == [f"Paragraph {i}" for i in range(1, 6)]


def test_bm25_ranks_relevant_first():
    docs = [tokens(t) for t in ["refund of price for defective goods", "lease deposit return", "criminal trial procedure"]]
    sc = BM25(docs).scores(tokens("refund defective goods"))
    assert max(sc, key=sc.get) == 0


def test_temporal_validation():
    mk = lambda **k: {"doc_type": "statute", "status": "in_force", "effective_from": None, "effective_to": None, "status_note": "", **k}  # noqa: E731
    today = date(2025, 1, 1)
    assert source_validity(mk(), today, False) == (True, None)
    assert source_validity(mk(status="repealed"), today, False)[0] is False
    assert source_validity(mk(status="repealed"), today, True)[0] is True  # explicit historical search
    assert source_validity(mk(effective_to=date(2024, 6, 30)), today, False)[0] is False
    assert source_validity(mk(effective_from=date(2026, 1, 1)), today, False)[0] is False
    ok, warn = source_validity(mk(status="superseded"), today, False)
    assert ok and "superseded" in warn
    assert source_validity(mk(status="unknown"), today, False)[1]  # unverified status is surfaced, not hidden
    assert source_validity({**mk(), "doc_type": "judgment", "status": "repealed"}, today, False)[0] is True


class TestCitationValidator:
    P = [{"n": 1, "text": "The seller shall refund the price within fifteen days of the demand.", "url": "https://x.example/a"}]

    def test_valid_quote_and_marker(self):
        r = CitationValidator(self.P).validate('See [S1]: "refund the price within fifteen days".', [(1, "refund the price within fifteen days")])
        assert r.validity == 1.0 and not r.issues

    def test_invented_marker_quote_url_and_section_are_stripped_or_flagged(self):
        v = CitationValidator(self.P)
        r = v.validate('The seller must pay damages [S7] as held in "twice the price" see https://made-up.example/x and Section 420 of the Imaginary Act, 1999.',
                       [(1, "twice the price")])
        assert r.validity < 1 and "[S7]" not in r.cleaned and "made-up.example" not in r.cleaned
        assert "[unsupported quotation removed]" in r.cleaned
        joined = " ".join(r.issues)
        assert "no such retrieved source" in joined and "not found in that passage" in joined and "unsupported statutory reference" in joined

    def test_elided_quote_segments_each_verified(self):
        v = CitationValidator(self.P)
        assert v.quote_supported(1, "The seller shall refund […] within fifteen days of the demand.")
        assert not v.quote_supported(1, "The seller shall refund […] within ninety days of the demand.")
        assert not v.quote_supported(1, "within fifteen days of the demand. The seller shall refund")  # text reordered without an elision marker is rejected

    def test_generated_sentences_without_valid_citation_are_dropped(self):
        v = CitationValidator(self.P)
        kept, dropped = v.require_citations("The seller must refund within fifteen days [S1]. The court always favours consumers. It also awards damages [S9].")
        assert kept == "The seller must refund within fifteen days [S1]."
        assert len(dropped) == 2  # an uncited claim and one citing a source that was never retrieved

    def test_allowed_url_kept(self):
        r = CitationValidator(self.P).validate("Read https://x.example/a [S1]")
        assert "https://x.example/a" in r.cleaned and r.validity == 1.0


def test_retrieval_filters_and_synthetic_hidden_in_production(client, monkeypatch):
    from app.config import get_settings

    r = client.get("/api/library/search", params={"q": "refund price defective goods"}).json()
    assert r["results"] and r["results"][0]["source"]["is_synthetic"] is True and "Refund" in r["results"][0]["source"]["title"]
    assert not client.get("/api/library/search", params={"q": "refund price defective goods", "doc_type": "judgment"}).json()["results"]
    monkeypatch.setattr(get_settings(), "include_synthetic_corpus", False)
    assert not client.get("/api/library/search", params={"q": "refund price defective goods"}).json()["results"]
    assert client.get("/api/library/sources").json()["total"] == 0  # synthetic fixtures never listed as real sources


def test_ask_grounded_with_validated_citations(client, user):
    r = client.post("/api/ask", json={"question": "Can I get a refund of the price for defective goods from the seller?"}).json()
    assert r["status"] == "ok" and r["citations"] and r["citation_report"]["validity"] == 1.0
    c = r["citations"][0]
    assert c["url"].startswith("https://example.invalid/") and c["synthetic"] is True
    assert any("synthetic" in u.lower() for u in r["sections"]["uncertainties"])
    assert r["disclaimer"] and r["sections"]["professional_advice"]
    assert all(m["model"].startswith("law-ai/") for m in r["models_used"])
    # conversation history persisted with the structured payload
    conv = client.get(f"/api/conversations/{r['conversation_id']}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"] and conv["messages"][1]["payload"]["citations"]


def test_ask_declines_when_evidence_is_insufficient(client, user):
    r = client.post("/api/ask", json={"question": "What is the law on interplanetary salvage of asteroid mining rights?"}).json()
    assert r["status"] == "insufficient_evidence" and r["answer"] is None and r["citations"] == []
    assert "do not contain enough" in r["message"]


def test_urgent_contacts_and_clarifying_questions(client, user):
    r = client.post("/api/ask", json={"question": "Someone made an unauthorised transaction and money deducted from my UPI account"}).json()
    assert any(c["number"] == "1930" for c in r["urgent_contacts"]) and r["clarifying_questions"]


def test_ask_validation(client, user):
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert client.post("/api/ask", json={"question": "valid question here?", "translate_to": "xx"}).status_code == 422


def test_legal_language_score_is_advisory_and_only_words_a_decline(client, user, monkeypatch):
    """CustomInLawBERT's score never blocks a grounded answer (as a hard gate it rejected valid doctrinal questions); it only words a decline."""
    from app.rag import pipeline

    monkeypatch.setattr(pipeline, "legal_language_check", lambda db, q: {"model": "law-ai/CustomInLawBERT", "score": 0.40, "threshold": 0.62, "looks_legal": False})
    ok = client.post("/api/ask", json={"question": "Can I get a refund of the price for defective goods from the seller?"}).json()
    assert ok["status"] == "ok" and ok["citations"] and ok["domain_check"]["looks_legal"] is False  # still answered: evidence is what gates
    no = client.post("/api/ask", json={"question": "What is the law on interplanetary salvage of asteroid mining rights?"}).json()
    # The detector is wrong too often to be shown to users as a claim ("this isn't a legal question"): the message says what is loaded instead.
    assert no["status"] == "insufficient_evidence" and "doesn't look like" not in no["message"] and "do not contain enough" in no["message"]
    assert "Acts" in no["message"] or "No Acts are loaded" in no["message"] or "rephrasing" in no["message"]


def test_topic_identification_uses_real_model_when_installed(models_present):
    if not models_present:
        import pytest
        pytest.skip("model weights not downloaded")
    from app.rag.pipeline import identify_topic

    t = identify_topic("My landlord has not returned my security deposit after I vacated the flat and handed over the keys.")
    assert t["model"] == "law-ai/InCaseLawBERT" and t["topic"] == "tenancy" and t["ranked"]
    t = identify_topic("The shop refuses a refund for a defective laptop under warranty.")
    assert t["topic"] == "consumer"


def test_gate_thresholds_and_roles_are_configured():
    from app import runtime
    from app.config import get_settings

    s = get_settings()
    assert s.min_query_coverage == 0.45 and s.domain_threshold == 0.62 and s.center_embeddings is False
    assert runtime.RETRIEVAL_COMPONENTS == ["bm25"] or "bm25" in runtime.RETRIEVAL_COMPONENTS  # tests override to BM25-only


def test_uncited_generated_answer_falls_back_to_verbatim_excerpts(client, user, monkeypatch):
    """A free-text generator that ignores the citation rule must never be shown as 'verified'."""
    from app.rag import pipeline

    class Uncited:
        name = "local_llm"

        def generate(self, question, passages):
            return {"text": "Consumers are always entitled to a refund in every case.", "quotes": [], "mode": "local_llm", "note": "generated"}

    monkeypatch.setattr(pipeline, "get_generator", lambda: Uncited())
    r = client.post("/api/ask", json={"question": "Can I get a refund of the price for defective goods from the seller?"}).json()
    assert r["status"] == "ok" and r["answer_mode"] == "extractive"
    assert "always entitled" not in r["answer"] and "no statement that could be tied to a source" in r["answer_note"]
    assert any("no cited statements" in i for i in r["citation_report"]["issues"])


def test_cited_generated_answer_is_kept(client, user, monkeypatch):
    from app.rag import pipeline

    class Cited:
        name = "local_llm"

        def generate(self, question, passages):
            return {"text": "The seller must refund the price within fifteen days of the demand [S1]. Nobody can promise the result.", "quotes": [], "mode": "local_llm", "note": "generated"}

    monkeypatch.setattr(pipeline, "get_generator", lambda: Cited())
    r = client.post("/api/ask", json={"question": "Can I get a refund of the price for defective goods from the seller?"}).json()
    assert r["answer_mode"] == "local_llm" and r["answer"] == "The seller must refund the price within fifteen days of the demand [S1]."
    assert r["citation_report"]["valid"] == 1 and any("1 generated sentence" in i for i in r["citation_report"]["issues"])
