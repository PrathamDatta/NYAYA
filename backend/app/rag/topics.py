"""Topic prototypes (for CustomLegalNLP), fact-gathering questions and non-legal procedural pointers.

These are product scaffolding, not statements of law. Helplines come from the previous version of the product
(see app/data/legal_aid_directory.json) and are shown with that provenance."""
from __future__ import annotations

import re

TOPICS: dict[str, str] = {
    "consumer": "A buyer complains about defective goods or deficient service, seeks refund, replacement or compensation from a seller, manufacturer or e-commerce platform under consumer protection law.",
    "tenancy": "A landlord and tenant dispute over rent, eviction, notice of vacation, return of the security deposit and possession of rented premises under a lease or rent agreement.",
    "contract": "A dispute about breach of contract, unpaid invoices, non-payment for work or services delivered, damages and recovery of money due under an agreement.",
    "cyber_fraud": "Online financial fraud, unauthorised UPI or bank transfers, phishing, impersonation, identity theft and cheating by using a computer resource or mobile phone.",
    "criminal": "A criminal offence such as cheating, theft, assault, criminal breach of trust or intimidation, registration of a first information report with the police, investigation, arrest and bail.",
    "family": "Domestic violence, marriage, divorce, maintenance, custody of children, dowry harassment and protection of women within the household.",
    "employment": "Wages, termination of employment, notice period, dismissal, workplace harassment and disputes between an employer and an employee.",
    "property": "Ownership, title, sale, partition, possession, boundary and encroachment disputes relating to land, houses or immovable property.",
}

QUESTIONS: dict[str, list[str]] = {
    "consumer": ["When and where did you buy the product or service, and what did you pay (invoice or receipt)?",
                 "Was it bought for personal use or for business/resale?",
                 "Have you complained in writing to the seller, and what was the reply?"],
    "tenancy": ["Is there a written rent agreement, and what does it say about notice and the deposit?",
                "When did you give notice and hand over possession, and is there proof (email, receipt, inspection)?",
                "In which State and city is the property?"],
    "contract": ["Is there a written agreement, invoice or email confirming the work or price?",
                 "What was delivered, on what date, and how did the other party acknowledge it?",
                 "Have you sent a written demand, and when?"],
    "cyber_fraud": ["When did the transaction happen, and have you reported it to your bank and to the national cyber-crime portal?",
                    "Do you have transaction IDs (UTR/UPI reference), phone numbers or screenshots?"],
    "criminal": ["What happened, when, and where (police station area)?",
                 "Has a police complaint or FIR already been made? If yes, what is its number and date?",
                 "Did the events happen before or after 1 July 2024? (This affects which criminal statute may apply.)"],
    "family": ["Are you or anyone in immediate danger right now?", "Which State are you in, and is there any existing court order?"],
    "employment": ["Do you have an appointment letter or payslips?", "When did the dispute begin and what notice or reason was given?"],
    "property": ["Do you hold title documents or a registered deed?", "Is anyone currently in possession, and since when?"],
}

URGENT = [
    (re.compile(r"(?i)beaten|domestic violence|in-laws|abuse at home|threaten(ed)? to kill|immediate danger"),
     {"label": "Emergency (police)", "number": "112"}, {"label": "Women Helpline (All India)", "number": "181"}),
    (re.compile(r"(?i)unauthori[sz]ed (debit|transaction)|money deducted|upi fraud|scammed|lost money|otp"),
     {"label": "National Cyber Crime Reporting Helpline", "number": "1930"}, None),
    (re.compile(r"(?i)summons|hearing (is )?tomorrow|bailable warrant|arrest(ed)?|limitation (is )?expir"),
     {"label": "National Legal Aid Helpline (NALSA)", "number": "15100"}, None),
]


def urgent_contacts(text: str) -> list[dict]:
    out: list[dict] = []
    for pat, a, b in URGENT:
        if pat.search(text):
            out.append(a)
            if b:
                out.append(b)
    return out


KEYWORDS: dict[str, tuple[str, ...]] = {
    "consumer": ("refund", "defective", "warranty", "consumer", "product", "seller", "e-commerce", "deficiency"),
    "tenancy": ("landlord", "tenant", "rent", "lease", "deposit", "eviction", "flat", "vacat"),
    "contract": ("invoice", "contract", "agreement", "freelanc", "unpaid", "payment due", "breach"),
    "cyber_fraud": ("upi", "otp", "phishing", "cyber", "online fraud", "scam", "hacked"),
    "criminal": ("fir", "police", "cheat", "theft", "assault", "arrest", "bail", "threat"),
    "family": ("husband", "wife", "divorce", "maintenance", "custody", "dowry", "domestic"),
    "employment": ("salary", "wages", "employer", "terminat", "dismiss", "resign", "notice period"),
    "property": ("property", "land", "title", "partition", "encroach", "possession", "sale deed"),
}


def keyword_topic(text: str) -> list[tuple[str, int]]:
    low = text.lower()
    sc = {t: sum(1 for k in ks if k in low) for t, ks in KEYWORDS.items()}
    return sorted(((t, n) for t, n in sc.items() if n), key=lambda x: -x[1])
