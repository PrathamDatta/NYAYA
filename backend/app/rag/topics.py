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
    (re.compile(r"(?i)\brob(bed|bery)?\b|attack(ed)?\b|assault|kidnap|abduct|\brape|molest|stabbed|shot at|being followed"),
     {"label": "Emergency (police)", "number": "112"}, None),
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


# ---------------------------------------------------------------------------------------------------------------------
# "Which area of law is this?" — general orientation shown for EVERY question, clearly labelled as general guidance that
# does NOT come from the loaded library. Act names only (no section numbers): section-level statements must come from sources.
# ---------------------------------------------------------------------------------------------------------------------
AREAS: dict[str, dict] = {
    "consumer": {"label": "Consumer protection law", "laws": ["Consumer Protection Act, 2019", "Sale of Goods Act, 1930"]},
    "tenancy": {"label": "Landlord–tenant (rent and lease) law",
                "laws": ["Transfer of Property Act, 1882 (leases)", "Your State's Rent Control / Rent Act", "Indian Contract Act, 1872 (the rent agreement)"]},
    "contract": {"label": "Contract law and recovery of money",
                 "laws": ["Indian Contract Act, 1872", "Code of Civil Procedure, 1908 (suits for recovery)", "Limitation Act, 1963 (time limits)"]},
    "cyber_fraud": {"label": "Cyber crime and online fraud",
                    "laws": ["Information Technology Act, 2000", "Bharatiya Nyaya Sanhita, 2023 (cheating and related offences)"]},
    "criminal": {"label": "Criminal law",
                 "laws": ["Bharatiya Nyaya Sanhita, 2023 (the offences)", "Bharatiya Nagarik Suraksha Sanhita, 2023 (FIR, investigation, bail, trial)",
                          "Bharatiya Sakshya Adhiniyam, 2023 (evidence)"]},
    "family": {"label": "Family law and protection of women",
               "laws": ["Protection of Women from Domestic Violence Act, 2005", "Personal laws on marriage, divorce and maintenance (depend on religion)",
                        "Bharatiya Nyaya Sanhita, 2023 (cruelty and related offences)"]},
    "employment": {"label": "Employment and labour law", "laws": ["Central and State labour laws on wages, termination and industrial disputes"]},
    "property": {"label": "Property law", "laws": ["Transfer of Property Act, 1882", "Registration Act, 1908", "Specific Relief Act, 1963"]},
}

BNS_NOTE = ("For events on or after 1 July 2024, criminal offences are governed by the Bharatiya Nyaya Sanhita, 2023; "
            "for earlier events, the Indian Penal Code, 1860 applies.")

# (pattern, offence category, plain-language note). Categories, not section numbers.
OFFENCES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"(?i)\brob(bed|bery|bing)?\b|snatch|mugged|held me up|loot"), "Robbery / theft (offences against property)",
     "Taking property by force or threat is robbery; taking it without force is theft."),
    (re.compile(r"(?i)\bstole|stolen|\btheft\b|pickpocket|burglar|break-?in|broke into"), "Theft / house-breaking (offences against property)", ""),
    (re.compile(r"(?i)assault|\bbeat(en|ing)?\b|\bhit me|punch|slap|attack(ed)?\b|\bhurt\b|injur|battery|thrash"), "Hurt and assault (offences against the human body)",
     "Indian law speaks of “hurt”, “grievous hurt”, “assault” and “criminal force” — it does not use the term “battery”."),
    (re.compile(r"(?i)threat|threaten|blackmail|extort"), "Criminal intimidation / extortion (threats)", ""),
    (re.compile(r"(?i)cheat|fraud|scam|duped|conned|\bfake\b"), "Cheating / fraud", ""),
    (re.compile(r"(?i)defam|slander|libel|false rumou?r|insult"), "Defamation / insult", ""),
    (re.compile(r"(?i)stalk|follow(ed|s|ing) me|eve-?teas|keeps? (calling|messaging|texting|sending)|unwanted (calls|messages)|sending me messages"),
     "Stalking / harassment", ""),
    (re.compile(r"(?i)kidnap|abduct"), "Kidnapping / abduction", ""),
    (re.compile(r"(?i)\brape|molest|sexual|groped|grope|outrag"), "Sexual offences (urgent — help is available)", ""),
    (re.compile(r"(?i)murder|killed|homicide|\bdeath\b|dead body"), "Offences affecting life (homicide)", ""),
    (re.compile(r"(?i)trespass|encroach|entered my (house|land|property)"), "Criminal trespass", ""),
    (re.compile(r"(?i)dowry|cruelty|in-?laws"), "Cruelty / dowry harassment", ""),
]


def classify_offences(text: str) -> list[dict]:
    out, seen = [], set()
    for pat, label, note in OFFENCES:
        if pat.search(text) and label not in seen:
            seen.add(label)
            out.append({"offence": label, "note": note})
    return out


def area_of_law(question: str, topic: str | None, confidence: str, looks_legal: bool | None = None) -> dict:
    """Always returns something useful, but never invents certainty.

    An explicit offence match (robbed, hit, threatened...) outranks a low-confidence embedding guess. If nothing matches and the
    embedding topic is only a low-confidence guess, the area is reported as unclear, with the guess shown as such."""
    offences = classify_offences(question)
    key, conf = topic, confidence
    if offences:
        if not (topic in ("cyber_fraud", "family") and confidence in ("high", "medium")):
            key, conf = "criminal", "medium"
        else:
            conf = confidence
    area = AREAS.get(key or "")
    guess = None
    if not offences and confidence == "low" and area:  # only an embedding guess: do not present it as a finding
        guess, area, key = area["label"], None, None
    label = area["label"] if area else ("This doesn't look like a legal matter" if looks_legal is False and guess else "Area of law not clear from this description")
    return {
        "key": key, "label": label, "laws": area["laws"] if area else [], "offences": offences, "confidence": conf if area else "low",
        "closest_guess": guess if guess else None,
        "note": BNS_NOTE if key in ("criminal", "cyber_fraud", "family") or offences else
                ("Add who was involved, what happened, when and where, and what you want to achieve — that lets the area be identified." if not area else ""),
        "source": "General orientation by the app — NOT drawn from the loaded legal library. Check the Acts on India Code before relying on it.",
    }


# Legal vocabulary used to ENRICH the retrieval query once an offence or area is recognised, so that lay words ("robbed") reach legal text
# ("robbery", "dacoity", "extortion"). Retrieval-only; it is never shown as a finding.
OFFENCE_TERMS = {  # SPECIFIC legal words only: generic ones (property, force, fear) drown out the rare terms that matter
    "Robbery / theft": "robbery dacoity theft extortion snatching",
    "Theft / house-breaking": "theft stolen burglary house-breaking",
    "Hurt and assault": "hurt grievous assault injuries",
    "Criminal intimidation": "criminal intimidation threat",
    "Cheating / fraud": "cheating fraud deception",
    "Defamation": "defamation",
    "Stalking": "stalking outraging modesty",
    "Sexual offences": "rape sexual assault modesty",
    "Kidnapping": "kidnapping abduction",
    "Offences affecting life": "murder homicide",
    "Criminal trespass": "trespass",
    "Cruelty / dowry": "dowry cruelty",
}
AREA_TERMS = {
    "tenancy": "lessor lessee tenancy eviction landlord tenant",
    "consumer": "consumer deficiency defect refund",
    "contract": "contract breach damages",
    "cyber_fraud": "cyber cheating impersonation",
    "criminal": "offence accused prosecution",
    "family": "maintenance cruelty custody domestic",
    "employment": "workman wages termination employer",
    "property": "title possession partition encroachment",
}


def concept_terms(question: str, topic: str | None, confidence: str) -> list[str]:
    """Legal words that should also be searched for, given what the question describes."""
    words: list[str] = []
    for o in classify_offences(question):
        for key, terms in OFFENCE_TERMS.items():
            if o["offence"].startswith(key) or key.split(" /")[0] in o["offence"]:
                words += terms.split()
    if topic and (confidence in ("high", "medium") or not words):
        words += AREA_TERMS.get(topic, "").split()
    return list(dict.fromkeys(words))
