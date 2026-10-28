from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import H, new_client


def test_register_login_logout(client):
    r = client.post("/api/auth/register", json={"email": "A@Example.com", "password": "a-long-password-1"})
    assert r.status_code == 201 and r.json()["email"] == "a@example.com"
    assert "password" not in r.text
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    ok = client.post("/api/auth/login", json={"email": "a@example.com", "password": "a-long-password-1"})
    assert ok.status_code == 200
    bad = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong"})
    nouser = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert bad.status_code == nouser.status_code == 401 and bad.json()["error"]["message"] == nouser.json()["error"]["message"]


def test_duplicate_and_weak_password(client):
    client.post("/api/auth/register", json={"email": "d@example.com", "password": "a-long-password-1"})
    assert client.post("/api/auth/register", json={"email": "d@example.com", "password": "a-long-password-1"}).status_code == 409
    r = client.post("/api/auth/register", json={"email": "e@example.com", "password": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_session_cookie_flags(client):
    r = client.post("/api/auth/register", json={"email": "c@example.com", "password": "a-long-password-1"})
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc


def test_csrf_header_required(corpus):
    c = TestClient(create_app(), base_url="http://testserver")  # no X-Requested-With
    r = c.post("/api/auth/register", json={"email": "x@example.com", "password": "a-long-password-1"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf"
    r = c.post("/api/auth/login", json={"email": "x@example.com", "password": "x"}, headers={**H, "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_private_routes_need_auth(client):
    for path in ("/api/conversations", "/api/documents", "/api/drafts", "/api/cases", "/api/auth/export"):
        assert client.get(path).status_code == 401, path
    assert client.post("/api/ask", json={"question": "hello world?"}).status_code == 401


def test_rate_limit(monkeypatch, corpus):
    from app.config import get_settings
    from app.security import limiter

    monkeypatch.setattr(get_settings(), "auth_rate_limit_per_minute", 3)
    limiter.reset()
    c = new_client(corpus)
    codes = [c.post("/api/auth/login", json={"email": "z@example.com", "password": "nope"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_sql_injection_like_input_is_inert(client, user):
    r = client.post("/api/auth/login", json={"email": "' OR 1=1 --", "password": "x"})
    assert r.status_code == 401
    assert client.get("/api/library/sources", params={"q": "'; DROP TABLE users; --"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200
