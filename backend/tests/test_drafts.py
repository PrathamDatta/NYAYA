import io

import docx

FACTS = {"complainant_name": "Asha Rao", "complainant_address": "12 MG Road, Bengaluru", "opponent_name": "OmniKart Retail Pvt. Ltd.",
         "opponent_address": "Outer Ring Road, Bengaluru", "facts": "Laptop stopped working on 30 Aug 2024.", "amount": "84999",
         "deadline_days": "15", "relief": "refund the price", "date_of_notice": "01/09/2024"}


def test_templates_listed(client):
    t = client.get("/api/drafts/templates").json()
    assert {x["id"] for x in t} == {"legal_notice", "consumer_complaint", "police_complaint", "money_recovery_plaint"}
    assert all(x["fields"] for x in t)


def test_missing_facts_marked_and_listed(client, user):
    d = client.post("/api/drafts", json={"template_id": "legal_notice", "facts": {"complainant_name": "Asha"}}).json()
    assert "[●MISSING:" in d["content"] and "Other party's full name / company" in d["missing"]
    assert d["content"].startswith("DRAFT FOR REVIEW")


def test_complete_draft_edit_revisions_and_export(client, user):
    d = client.post("/api/drafts", json={"template_id": "legal_notice", "facts": FACTS}).json()
    assert d["missing"] == [] and "OmniKart" in d["content"] and "84999" in d["content"]
    u = client.put(f"/api/drafts/{d['id']}", json={"content": d["content"] + "\nAdditional paragraph by user."}).json()
    assert "Additional paragraph" in u["content"] and u["revisions"] >= 2
    docx_bytes = client.get(f"/api/drafts/{d['id']}/export?format=docx")
    assert docx_bytes.status_code == 200 and "wordprocessingml" in docx_bytes.headers["content-type"]
    text = "\n".join(p.text for p in docx.Document(io.BytesIO(docx_bytes.content)).paragraphs)
    assert "Additional paragraph" in text and "Verification checklist" in text
    assert client.get(f"/api/drafts/{d['id']}/export?format=pdf").status_code == 422  # unsupported formats are refused, not faked


def test_authorities_not_in_corpus_are_flagged_unverified(client, user):
    d = client.post("/api/drafts", json={"template_id": "consumer_complaint", "facts": {}}).json()
    assert d["authorities"] and all(not a["verified_in_corpus"] and "NOT found" in a["note"] for a in d["authorities"])


def test_unknown_template_rejected(client, user):
    assert client.post("/api/drafts", json={"template_id": "nope"}).status_code == 422
