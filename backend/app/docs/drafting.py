"""Structured drafting. Templates produce a *draft for review*; nothing is filed, served or submitted."""
from __future__ import annotations

import io
import re
from typing import Any

BANNER = "DRAFT FOR REVIEW — NOT FILED, SERVED OR APPROVED. Prepared with an automated drafting aid; have a qualified advocate review before use."
MISSING = "[●MISSING: {label}]"

F = lambda key, label, help="", required=True, kind="text": {"key": key, "label": label, "help": help, "required": required, "type": kind}  # noqa: E731

COMMON_PARTIES = [F("complainant_name", "Your full name"), F("complainant_address", "Your address", kind="textarea"),
                  F("opponent_name", "Other party's full name / company"), F("opponent_address", "Other party's address", kind="textarea")]

TEMPLATES: dict[str, dict[str, Any]] = {
    "legal_notice": {
        "title": "Legal demand notice",
        "description": "A formal notice demanding payment, refund or performance within a stated time.",
        "fields": COMMON_PARTIES + [
            F("facts", "What happened (dated, in your own words)", kind="textarea"),
            F("amount", "Amount demanded (₹)", "Digits only, e.g. 120000"),
            F("deadline_days", "Days allowed to comply", "Commonly 15 or 30", required=True),
            F("relief", "What you want them to do", kind="textarea"),
            F("date_of_notice", "Date of this notice (DD/MM/YYYY)")],
        "authorities": [{"label": "Indian Contract Act, 1872", "query": "Indian Contract Act 1872"},
                        {"label": "Transfer of Property Act, 1882", "query": "Transfer of Property Act 1882"}],
        "body": """LEGAL NOTICE

Date: {date_of_notice}
To: {opponent_name}
Address: {opponent_address}

From: {complainant_name}, {complainant_address}

Subject: Notice demanding {relief}

Sir/Madam,

1. I, {complainant_name}, state the following facts:
{facts}

2. By reason of the above, an amount of ₹{amount} is claimed from you.

3. You are called upon to {relief} within {deadline_days} days of receipt of this notice, failing which I may be compelled to take such legal steps as are available to me, at your risk as to costs and consequences.

4. This notice is issued without prejudice to my other rights and remedies.

{complainant_name}
""",
    },
    "consumer_complaint": {
        "title": "Consumer complaint (District Commission)",
        "description": "Complaint for defective goods or deficient service, with the facts and relief sought.",
        "fields": COMMON_PARTIES + [
            F("district", "District where you will file"), F("purchase_date", "Date of purchase (DD/MM/YYYY)"),
            F("price", "Price paid (₹)"), F("facts", "Facts of the defect / deficiency", kind="textarea"),
            F("prior_complaints", "Complaints already made to the seller (dates, replies)", kind="textarea"),
            F("relief", "Relief sought (refund, replacement, compensation)", kind="textarea")],
        "authorities": [{"label": "Consumer Protection Act, 2019", "query": "Consumer Protection Act 2019"}],
        "body": """BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION, {district}

{complainant_name}, {complainant_address}                      ...Complainant
Versus
{opponent_name}, {opponent_address}                           ...Opposite Party

COMPLAINT

1. The Complainant purchased the goods/services on {purchase_date} for ₹{price}.

2. Facts:
{facts}

3. Steps already taken by the Complainant:
{prior_complaints}

4. The Complainant therefore prays that this Commission may be pleased to grant:
{relief}

Place: {district}
Date: ____________
Complainant: {complainant_name}
""",
    },
    "police_complaint": {
        "title": "Complaint to police (for FIR registration)",
        "description": "A written complaint describing the incident for submission to the police station.",
        "fields": [F("complainant_name", "Your full name"), F("complainant_address", "Your address", kind="textarea"),
                   F("police_station", "Police station / officer addressed"), F("incident_date", "Date of incident (DD/MM/YYYY)"),
                   F("incident_place", "Place of incident"), F("accused", "Name/details of the accused (or 'unknown')"),
                   F("facts", "What happened, in order", kind="textarea"), F("loss", "Loss suffered (₹ / description)", required=False),
                   F("evidence", "Documents or evidence enclosed", kind="textarea", required=False)],
        "authorities": [{"label": "Bharatiya Nagarik Suraksha Sanhita, 2023", "query": "Bharatiya Nagarik Suraksha Sanhita 2023"},
                        {"label": "Bharatiya Nyaya Sanhita, 2023", "query": "Bharatiya Nyaya Sanhita 2023"}],
        "body": """To,
The Station House Officer,
{police_station}

Subject: Complaint regarding incident dated {incident_date} at {incident_place}

Respected Sir/Madam,

I, {complainant_name}, resident of {complainant_address}, wish to report the following:

{facts}

Accused: {accused}
Loss suffered: {loss}
Documents enclosed: {evidence}

I request that the information above be recorded and appropriate action be taken in accordance with law, and that I be given a copy of the record.

Yours faithfully,
{complainant_name}
""",
    },
    "money_recovery_plaint": {
        "title": "Plaint for recovery of money (outline)",
        "description": "Outline of a civil plaint for unpaid dues. Needs an advocate before filing.",
        "fields": COMMON_PARTIES + [F("court", "Court (e.g. District Court, city)"), F("agreement_date", "Date of agreement / invoice"),
                                    F("amount", "Principal amount due (₹)"), F("facts", "Facts of the transaction and non-payment", kind="textarea"),
                                    F("demand_date", "Date of written demand / notice", required=False),
                                    F("relief", "Relief sought", kind="textarea")],
        "authorities": [{"label": "Code of Civil Procedure, 1908", "query": "Code of Civil Procedure 1908"},
                        {"label": "Limitation Act, 1963", "query": "Limitation Act 1963"}],
        "body": """IN THE COURT OF {court}

{complainant_name}, {complainant_address}                      ...Plaintiff
Versus
{opponent_name}, {opponent_address}                           ...Defendant

PLAINT FOR RECOVERY OF ₹{amount}

1. The Plaintiff and Defendant entered into an agreement / transaction dated {agreement_date}.

2. Facts:
{facts}

3. A written demand was made on {demand_date}.

4. The cause of action arose on the dates stated above. [●CONFIRM limitation and jurisdiction with an advocate]

5. The Plaintiff prays for:
{relief}

Plaintiff: {complainant_name}
""",
    },
}


def public_templates() -> list[dict]:
    return [{"id": k, "title": v["title"], "description": v["description"], "fields": v["fields"],
             "authorities": [a["label"] for a in v["authorities"]]} for k, v in TEMPLATES.items()]


def render(template_id: str, facts: dict[str, str]) -> tuple[str, list[str]]:
    t = TEMPLATES[template_id]
    missing: list[str] = []
    values: dict[str, str] = {}
    for f in t["fields"]:
        v = (facts.get(f["key"]) or "").strip()
        if not v:
            if f["required"]:
                missing.append(f["label"])
            values[f["key"]] = MISSING.format(label=f["label"]) if f["required"] else "—"
        else:
            values[f["key"]] = v
    body = re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), t["body"])
    return f"{BANNER}\n\n{body}", missing


def check_authorities(db, template_id: str) -> list[dict]:
    """Verify each authority the template relies on against the ingested corpus (title/identifier match)."""
    from sqlalchemy import func, select

    from ..models import LegalSource

    out = []
    for a in TEMPLATES[template_id]["authorities"]:
        key = a["query"].lower().replace(",", "")
        rows = db.scalars(select(LegalSource).where(LegalSource.is_synthetic.is_(False), LegalSource.status != "archived",
                                                    func.lower(LegalSource.title).contains(key.split(" 19")[0].split(" 20")[0]))).all()
        found = rows[0] if rows else None
        out.append({"authority": a["label"], "verified_in_corpus": bool(found),
                    "source_url": found.source_url if found else None,
                    "note": "Found in the ingested corpus." if found else
                            "NOT found in the ingested corpus — verify the provisions you rely on against India Code before use."})
    return out


def to_docx(title: str, content: str, authorities: list[dict]) -> bytes:
    import docx
    from docx.shared import Pt

    d = docx.Document()
    d.core_properties.title = title
    for i, para in enumerate(content.split("\n")):
        p = d.add_paragraph(para)
        if i == 0:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    d.add_page_break()
    d.add_heading("Verification checklist (not part of the document)", level=2)
    for a in authorities:
        d.add_paragraph(f"{a['authority']}: {'found in corpus' if a['verified_in_corpus'] else 'NOT verified'} — {a['note']}")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
