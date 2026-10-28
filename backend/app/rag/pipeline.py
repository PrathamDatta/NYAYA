"""LegalResponsePipeline: normalise -> identify topic -> retrieve -> ground -> generate -> validate -> structure."""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..ml.encoders import CaseLawEncoder, CustomLegalNLP
from ..ml.registry import ModelUnavailableError
from .citations import CitationValidator
from .generator import ExtractiveGenerator, Passage, get_generator
from .index import get_index
from .rag_models import encoder
from .retriever import Filters, LegalRetriever
from .textutil import tokens
from .topics import QUESTIONS, TOPICS, keyword_topic, urgent_contacts

DISCLAIMER = ("This is legal information drawn from the sources shown, not legal advice. It may be incomplete or out of date, "
              "and it does not predict how any court or authority will decide your matter. Please consult a qualified "
              "advocate (free help may be available from your State Legal Services Authority) before acting.")


def identify_topic(question: str) -> dict[str, Any]:
    """Topic via InCaseLawBERT prototype similarity (best deployable classifier we measured), cross-checked with keyword evidence."""
    kw = keyword_topic(question)
    out: dict[str, Any] = {"model": None, "ranked": [], "keyword": kw[:2], "topic": kw[0][0] if kw else None, "confidence": "low"}
    try:
        nlp = encoder("incaselawbert")
        assert isinstance(nlp, CaseLawEncoder)
        ranked = nlp.classify_topic(question, TOPICS)
        out["model"] = "law-ai/InCaseLawBERT"
        out["ranked"] = [(t, round(s, 4)) for t, s in ranked[:3]]
        top = ranked[0][0]
        if kw and kw[0][0] == top:
            out["topic"], out["confidence"] = top, "high"
        elif kw:
            out["topic"], out["confidence"] = kw[0][0], "medium"  # explicit keywords outrank embedding similarity
        else:
            out["topic"], out["confidence"] = top, "low"
    except ModelUnavailableError as e:
        out["model_error"] = e.reason
    return out


def legal_language_check(db: Session, question: str) -> dict[str, Any]:
    """CustomInLawBERT legal-language score: cosine to the corpus centroid. Advisory; used to word a decline accurately."""
    out: dict[str, Any] = {"model": None, "score": None, "threshold": get_settings().domain_threshold, "looks_legal": None}
    try:
        nlp = encoder("custominlawbert")
        assert isinstance(nlp, CustomLegalNLP)
        centroid = get_index(db).centroid("custominlawbert")
        if centroid is None:
            out["note"] = "no CustomInLawBERT vectors indexed"
            return out
        out["model"] = "law-ai/CustomInLawBERT"
        out["score"] = round(nlp.legal_language_score(question, centroid), 4)
        if out["threshold"] is not None:
            out["looks_legal"] = out["score"] >= out["threshold"]
    except ModelUnavailableError as e:
        out["model_error"] = e.reason
    return out


class LegalResponsePipeline:
    def __init__(self) -> None:
        self.retriever = LegalRetriever()

    def answer(self, db: Session, question: str, filters: Filters | None = None, case_facts: dict | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        s = get_settings()
        question = question.strip()
        topic = identify_topic(question)
        domain = legal_language_check(db, question)
        timings["topic_s"] = round(time.perf_counter() - t0, 3)

        t1 = time.perf_counter()
        hits, rinfo = self.retriever.search(db, question, filters)
        timings["retrieval_s"] = round(time.perf_counter() - t1, 3)

        contacts = urgent_contacts(question)
        clarifying = list(QUESTIONS.get(topic["topic"] or "", []))
        resp: dict[str, Any] = {
            "question": question, "topic": topic, "domain_check": domain, "retrieval": rinfo, "disclaimer": DISCLAIMER,
            "urgent_contacts": contacts, "clarifying_questions": clarifying, "models_used": self._models_used(rinfo, topic, domain),
        }

        # Evidence sufficiency: the retrieved passages must jointly cover the question's content terms (IDF-weighted),
        # and every passage we cite must itself share vocabulary with the question.
        q_terms = set(tokens(question))
        coverage = rinfo.get("coverage", 0.0)
        hits = [h for h in hits if q_terms & set(tokens(h.text))]
        if not hits or coverage < s.min_query_coverage:  # the legal-language score is advisory: it only words the decline
            resp.update({
                "status": "insufficient_evidence", "answer": None, "citations": [], "sections": {},
                "message": (self._decline_message(db) if rinfo.get("corpus_chunks") else
                            "No legal sources have been ingested yet. See docs/INGESTION.md to load the corpus."),
                "timings": {**timings, "total_s": round(time.perf_counter() - t0, 3)},
            })
            return resp

        passages = [Passage(i + 1, h.text, h.ref_label, h.source["title"], h.source["source_url"]) for i, h in enumerate(hits)]
        t2 = time.perf_counter()
        gen = get_generator().generate(question, passages)
        timings["generation_s"] = round(time.perf_counter() - t2, 3)
        validator = CitationValidator([{"n": p.n, "text": p.text, "url": p.url} for p in passages])
        generation_notes: list[str] = []
        if gen["mode"] != "extractive":
            kept, dropped = validator.require_citations(gen["text"])
            if dropped:
                generation_notes.append(f"{len(dropped)} generated sentence(s) without a valid citation were removed.")
            if not kept:  # nothing verifiable survived: fall back openly to the verbatim excerpts
                gen = {**ExtractiveGenerator().generate(question, passages),
                       "note": "The text generator produced no statement that could be tied to a source, so verbatim excerpts are shown instead."}
                generation_notes.append("Generator output discarded: no cited statements.")
            else:
                gen = {**gen, "text": kept}
        rep = validator.validate(gen["text"], gen["quotes"])
        rep.issues.extend(generation_notes)

        citations = []
        for i, h in enumerate(hits, start=1):
            src = h.source
            citations.append({
                "n": i, "title": src["title"], "doc_type": src["doc_type"], "identifier": src["identifier"],
                "authority": src["authority"], "jurisdiction": src["jurisdiction"], "ref": h.ref_label,
                "pages": [h.page_start, h.page_end], "url": src["source_url"], "publication_date": src["publication_date"],
                "status": src["status"], "synthetic": src["is_synthetic"], "version": src["version"],
                "ingested_at": src["ingested_at"], "excerpt": h.text[:700], "warnings": h.warnings,
            })
        uncertainties = ["The answer is limited to the passages retrieved; other provisions or later amendments may apply.",
                         "Jurisdiction, dates and the specific facts of your case can change the outcome."]
        if rep.issues:
            uncertainties.append(f"{len(rep.issues)} automated citation check(s) flagged — see citation report.")
        uncertainties += [f"[S{i}] {w}" for i, h in enumerate(hits, 1) for w in h.warnings]
        if any(c["synthetic"] for c in citations):
            uncertainties.append("Some sources are synthetic test fixtures and are NOT real law.")
        resp.update({
            "status": "ok", "answer": rep.cleaned, "answer_mode": gen["mode"], "answer_note": gen["note"], "citations": citations,
            "citation_report": rep.public(),
            "sections": {"uncertainties": uncertainties,
                         "next_steps": self._next_steps(topic["topic"], contacts),
                         "professional_advice": "Because this involves your rights and deadlines, please have a qualified advocate review the specifics before you act."},
            "timings": {**timings, "total_s": round(time.perf_counter() - t0, 3)},
        })
        return resp

    @staticmethod
    def _decline_message(db: Session) -> str:
        """Say what is actually loaded. (The legal-language detector is deliberately NOT used to word this: it wrongly called valid legal questions non-legal.)"""
        from sqlalchemy import func, select

        from ..models import LegalSource

        syn = None if get_settings().include_synthetic_corpus else LegalSource.is_synthetic.is_(False)
        q = select(LegalSource.doc_type, func.count(LegalSource.id)).group_by(LegalSource.doc_type)
        counts = dict(db.execute(q.where(syn) if syn is not None else q).all())
        names = {"judgment": "Supreme Court judgments", "statute": "Acts", "rule": "rules", "notification": "notifications"}
        have = ", ".join(f"{n} {names.get(t, t)}" for t, n in counts.items()) or "no documents"
        msg = f"The loaded legal sources ({have}) do not contain enough to answer this reliably, so no answer is given."
        if not counts.get("statute"):
            msg += (" No Acts are loaded in this installation yet, so everyday disputes such as tenancy, consumer or cyber-fraud questions "
                    "cannot be answered from statute text. Try a question about a legal principle or court procedure, or load the relevant Acts (docs/INGESTION.md).")
        else:
            msg += " Try rephrasing with the Act, section or kind of dispute, or ask a legal-aid clinic."
        return msg

    @staticmethod
    def _next_steps(topic: str | None, contacts: list[dict]) -> list[str]:
        steps = ["Keep originals and dated copies of every document, message and receipt.",
                 "Write down a dated timeline of events while memories are fresh.",
                 "Check the official text of any provision on India Code before relying on a summary."]
        if contacts:
            steps.insert(0, "If you are in danger or money is leaving your account, call the numbers listed above now.")
        steps.append("Contact your District/State Legal Services Authority (NALSA helpline 15100) to ask whether you qualify for free legal aid.")
        return steps

    @staticmethod
    def _models_used(rinfo: dict, topic: dict, domain: dict) -> list[dict]:
        used = [{"model": "law-ai/" + {"inlegalbert": "InLegalBERT", "incaselawbert": "InCaseLawBERT", "custominlawbert": "CustomInLawBERT"}[c],
                 "role": "retrieval"} for c in rinfo.get("components", []) if c != "bm25" and c not in rinfo.get("skipped", {})]
        if topic.get("model"):
            used.append({"model": topic["model"], "role": "topic identification"})
        if domain.get("model"):
            used.append({"model": domain["model"], "role": "legal-language detection"})
        return used
