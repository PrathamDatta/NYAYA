import io

from .conftest import new_client


def _register(corpus, email):
    c = new_client(corpus)
    assert c.post("/api/auth/register", json={"email": email, "password": "a-long-password-1"}).status_code == 201
    return c


def test_cross_user_isolation(corpus):
    alice, bob = _register(corpus, "alice-iso@example.com"), _register(corpus, "bob-iso@example.com")
    case = alice.post("/api/cases", json={"title": "Alice case"}).json()
    doc = alice.post("/api/documents", files={"file": ("a.txt", io.BytesIO(b"Rent is Rs. 10,000 per month."), "text/plain")}).json()
    draft = alice.post("/api/drafts", json={"template_id": "legal_notice", "facts": {"complainant_name": "Alice"}}).json()
    conv = alice.post("/api/ask", json={"question": "Can a consumer get a refund for defective goods?"}).json()["conversation_id"]

    for method, url in [("get", f"/api/cases/{case['id']}"), ("get", f"/api/documents/{doc['id']}"), ("get", f"/api/drafts/{draft['id']}"),
                        ("get", f"/api/drafts/{draft['id']}/export"), ("get", f"/api/conversations/{conv}"),
                        ("delete", f"/api/cases/{case['id']}"), ("delete", f"/api/documents/{doc['id']}"),
                        ("delete", f"/api/drafts/{draft['id']}"), ("delete", f"/api/conversations/{conv}"),
                        ("post", f"/api/documents/{doc['id']}/retry")]:
        assert getattr(bob, method)(url).status_code == 404, (method, url)
    assert bob.get("/api/documents").json() == [] and bob.get("/api/cases").json() == []
    # bob cannot attach to or ask within alice's resources
    assert bob.post("/api/ask", json={"question": "anything at all?", "conversation_id": conv}).status_code == 404
    assert bob.post("/api/ask", json={"question": "anything at all?", "case_id": case["id"]}).status_code == 404
    assert bob.post("/api/drafts", json={"template_id": "legal_notice", "case_id": case["id"]}).status_code == 404
    # alice still has everything
    assert alice.get(f"/api/documents/{doc['id']}").status_code == 200


def test_account_deletion_removes_data_and_files(corpus):
    from app.config import get_settings

    c = _register(corpus, "gone@example.com")
    uid = c.get("/api/auth/me").json()["id"]
    c.post("/api/documents", files={"file": ("a.txt", io.BytesIO(b"Some private text content here."), "text/plain")})
    folder = get_settings().upload_path / str(uid)
    assert folder.exists() and any(folder.iterdir())
    assert c.delete("/api/auth/account").status_code == 204
    assert not folder.exists()
    assert c.get("/api/auth/me").status_code == 401
    assert c.post("/api/auth/login", json={"email": "gone@example.com", "password": "a-long-password-1"}).status_code == 401
