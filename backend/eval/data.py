"""Evaluation data.

1. Retrieval gold labels are derived from the corpus itself: Supreme Court Reports headnotes cite the paragraph each
   proposition summarises ("... [Para 20][1006-G]"). Each such headnote sentence becomes a query; the cited judgment
   paragraph(s) are the relevant passages. Headnote chunks are removed from the candidate pool so a query cannot match
   its own source text. This is weak supervision (editorial summaries, not real user questions) and is reported as such.
2. Topic and out-of-domain queries are small hand-written synthetic sets (public/synthetic data only).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalChunk, LegalSource

PARA_REF = re.compile(r"\[Paras?\s*([\d,\s&and\-–]+?)\]")


@dataclass
class Q:
    text: str
    source_id: int
    gold_chunks: set[int]


def _paras(s: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r"[,&]|\band\b", s):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if m and int(m.group(2)) - int(m.group(1)) <= 4:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            out.append(int(part))
    return out


def build_retrieval_queries(db: Session, max_queries: int = 400) -> list[Q]:
    qs: list[Q] = []
    for src in db.scalars(select(LegalSource).where(LegalSource.doc_type == "judgment")):
        chunks = db.scalars(select(LegalChunk).where(LegalChunk.source_id == src.id).order_by(LegalChunk.ordinal)).all()
        head = " ".join(c.text for c in chunks if c.ref_label.startswith("Preamble"))
        by_para: dict[int, set[int]] = {}
        for c in chunks:
            m = re.match(r"Paragraph (\d+)$", c.ref_label) or re.match(r"Paragraph (\d+) \(cont\.\)$", c.ref_label)
            if m:
                by_para.setdefault(int(m.group(1)), set()).add(c.id)
            m2 = re.match(r"Paragraphs (\d+)–(\d+)$", c.ref_label)
            if m2:
                for n in range(int(m2.group(1)), int(m2.group(2)) + 1):
                    by_para.setdefault(n, set()).add(c.id)
        prev = 0
        for m in PARA_REF.finditer(head):
            seg = head[prev:m.start()]
            prev = m.end()
            gold = set().union(*(by_para.get(n, set()) for n in _paras(m.group(1)))) if _paras(m.group(1)) else set()
            seg = re.sub(r"\[[^\]]*\]", " ", seg)  # drop other bracketed markers ([Para..], [1006-G])
            seg = re.sub(r"(?m)^.*\b(?:v\.|Appeal No|Petition|S\.C\.R\.).*$", " ", seg)  # case-title lines are not propositions
            seg = re.sub(r"(?m)^\s*\d+\.\d+\s+", " ", seg)  # item numbers such as 1.2
            words = re.sub(r"\s+", " ", seg).strip(" -–.").split()
            text = " ".join(words[-60:])
            if gold and len(words) >= 8:
                qs.append(Q(text, src.id, gold))
    return qs[:max_queries]


# Hand-written synthetic topic queries (label = topic key used by app.rag.topics.TOPICS)
TOPIC_QUERIES: dict[str, list[str]] = {
    "consumer": ["The laptop I bought stopped working in a month and the shop refuses a refund.", "An online store delivered a damaged phone and will not replace it.",
                 "The washing machine has a manufacturing defect and the company keeps delaying the repair under warranty.", "I paid for a coaching course that was never delivered as promised.",
                 "The e-commerce platform rejected my warranty claim without explanation.", "A builder gave a flat with poor fittings that do not match the brochure."],
    "tenancy": ["My landlord has not returned my security deposit after I vacated the flat.", "The landlord is trying to evict me without proper notice.",
                "I gave one month's notice to leave the rented house and handed over the keys but got no deposit back.", "The rent agreement says eleven months and the owner wants more rent now.",
                "My tenant has stopped paying rent for six months.", "The owner locked the shop I rent and removed my goods."],
    "contract": ["The client has not paid my freelance invoice even though I delivered the work.", "The supplier did not deliver goods as per the agreement and I want damages.",
                 "My company delivered the project milestone but the customer refuses to pay the balance.", "The other party cancelled the contract midway and keeps my advance.",
                 "A vendor is demanding payment for services that were never completed.", "We signed an agreement for supply of materials and the buyer defaulted on payment."],
    "cyber_fraud": ["Someone called pretending to be from my bank and took money through UPI.", "An unauthorised transaction was made from my account after I shared an OTP.",
                    "I received a phishing link and my card was charged.", "A fraudster impersonated my relative online and asked me to transfer money.",
                    "My social media account was hacked and used to cheat my friends.", "I paid an online seller who vanished after receiving the money."],
    "criminal": ["The police are refusing to register my complaint about theft.", "I want to file an FIR for cheating by a business partner.",
                 "A person threatened me with violence and I need to report it.", "My relative was arrested and I want to know how bail works.",
                 "Someone assaulted me in a dispute over parking.", "A trustee misused the funds entrusted to him."],
    "family": ["My husband beats me and the in-laws harass me for dowry.", "I want a divorce and maintenance for my children.",
               "My spouse has taken our child away and refuses to return.", "Can a wife claim maintenance after separation?", "A woman faces violence at home and needs protection.",
               "How is custody of a minor child decided between parents?"],
    "employment": ["My employer terminated me without notice or pay.", "The company has not paid my salary for three months.",
                   "I was dismissed after complaining about harassment at the workplace.", "My employer is withholding my experience letter and final settlement.",
                   "I resigned and the company is refusing to release my dues.", "Wages were deducted unlawfully from my monthly pay."],
    "property": ["A neighbour has encroached on my land boundary.", "I bought a plot but the seller's title is disputed.", "Co-heirs are refusing to partition ancestral property.",
                 "Someone is in unauthorised possession of my house.", "The sale deed of my plot has not been registered by the seller.", "A builder sold the same flat to two buyers."],
}

# Clearly unrelated queries the system must decline (no legal source can ground them)
OUT_OF_DOMAIN = [
    "Explain the taxation of cryptocurrency mining rigs on the moon?", "How do I bake a chocolate cake without eggs?", "What is the best football team in Europe?",
    "Which smartphone has the best camera under 20000 rupees?", "How to train a dog to stop barking at night?", "What is the capital of Australia?",
    "Recommend a good workout routine for building muscle.", "What is the boiling point of water at high altitude?", "How does photosynthesis work in desert plants?",
    "Give me a recipe for vegetable biryani for ten people.", "Which programming language should I learn first?", "What time does the sun set in Reykjavik in June?",
    "How can I improve my chess openings?", "What is the plot of the latest superhero movie?", "How many calories are in a banana?",
    "Explain how black holes form.", "Suggest names for a pet parrot.", "How do I repair a leaking kitchen tap?", "What is the distance between Mars and Earth?",
    "Which fertiliser is best for tomato plants?",
]
