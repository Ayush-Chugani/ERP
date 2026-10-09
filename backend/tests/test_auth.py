"""Authentication, session rotation, lockout, CSRF and password policy."""
import pytest

from app.core import totp
from tests.conftest import DEMO_PASSWORD, Client


def test_login_success_and_profile(client):
    r = client.login("registrar")
    assert set(r.json()) >= {"access", "expires_in", "csrfToken"}
    me = client.get("/auth/me").json()
    assert me["username"] == "registrar"
    assert "REGISTRAR" in me["roles"]
    assert me["permissions"] and "ADMISSION" in me["access_modules"]
    assert "password_hash" not in me
    # refresh cookie is HttpOnly and scoped to the auth path
    set_cookie = r.headers.get_list("set-cookie")
    refresh = next(c for c in set_cookie if c.startswith("sims_refresh="))
    assert "HttpOnly" in refresh and "Path=/api/v1/auth" in refresh and "SameSite=strict" in refresh


def test_wrong_password_and_unknown_user_are_indistinguishable(client):
    a = client.login("registrar", "wrong-password-1A!", expect=401)
    b = client.login("no-such-user", "wrong-password-1A!", expect=401)
    assert a.json() == b.json()


def test_login_requires_csrf(app):
    c = Client(app)
    r = c.http.post("/api/v1/auth/login", json={"username": "registrar", "password": DEMO_PASSWORD})
    assert r.status_code == 403
    r = c.http.post("/api/v1/auth/login", json={"username": "registrar", "password": DEMO_PASSWORD},
                    headers={"X-CSRF-Token": "forged.token"})
    assert r.status_code == 403


def test_cross_origin_login_rejected(client):
    r = client.http.post("/api/v1/auth/login", json={"username": "registrar", "password": DEMO_PASSWORD},
                         headers={"X-CSRF-Token": client.csrf, "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_lockout_after_repeated_failures(client, monkeypatch):
    for _ in range(5):
        client.login("student2", "bad-password-1A!!", expect=401)
    # the right password no longer works while locked
    client.login("student2", expect=401)


def test_protected_routes_need_a_token(client):
    assert client.get("/people/student").status_code == 401
    assert client.get("/auth/me").status_code == 401
    client.http.headers["Authorization"] = "Bearer not.a.jwt"
    assert client.get("/auth/me").status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    client.login("registrar")
    old_cookie = client.http.cookies.get("sims_refresh", path="/api/v1/auth")
    r = client.post("/auth/refresh", headers=client.csrf_headers())
    assert r.status_code == 200 and r.json()["access"]
    new_cookie = client.http.cookies.get("sims_refresh", path="/api/v1/auth")
    assert new_cookie != old_cookie
    # replaying the rotated-out token is treated as theft: the whole session dies
    client.http.cookies.set("sims_refresh", old_cookie, path="/api/v1/auth")
    assert client.post("/auth/refresh", headers=client.csrf_headers()).status_code == 401
    client.http.cookies.set("sims_refresh", new_cookie, path="/api/v1/auth")
    assert client.post("/auth/refresh", headers=client.csrf_headers()).status_code == 401
    assert client.get("/auth/me").status_code == 401  # access token is bound to the revoked session


def test_logout_revokes_session(client):
    client.login("hod")
    assert client.post("/auth/logout", headers=client.csrf_headers()).status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/refresh", headers=client.csrf_headers()).status_code == 401


def test_change_password_policy_and_effect(client):
    client.login("student2")
    r = client.post("/auth/change-password", json={"current_password": DEMO_PASSWORD, "new_password": "short"})
    assert r.status_code == 422 and "password" in r.json()["error"]["details"]
    r = client.post("/auth/change-password", json={"current_password": "nope-nope-nope1A!", "new_password": "Another#Pass2026"})
    assert r.status_code == 422
    r = client.post("/auth/change-password", json={"current_password": DEMO_PASSWORD, "new_password": DEMO_PASSWORD})
    assert r.status_code == 422  # reuse
    r = client.post("/auth/change-password", json={"current_password": DEMO_PASSWORD, "new_password": "Another#Pass2026"})
    assert r.status_code == 200
    fresh = Client(client.http.app)
    fresh.login("student2", expect=401)
    fresh.login("student2", "Another#Pass2026")


def test_session_listing_and_remote_revoke(app, db):
    a, b = Client(app), Client(app)
    a.login("teacher")
    b.login("teacher")
    sessions = a.get("/auth/sessions").json()["results"]
    assert len(sessions) >= 2 and sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert a.delete(f"/auth/sessions/{other['session_id']}", headers=a.csrf_headers()).status_code == 204
    assert b.get("/auth/me").status_code == 401
    assert a.get("/auth/me").status_code == 200


def test_mfa_enrolment_and_login(client, app):
    client.login("examcell")
    secret = client.post("/auth/mfa/setup").json()["secret"]
    assert client.post("/auth/mfa/enable", json={"code": "000000"}).status_code == 422
    assert client.post("/auth/mfa/enable", json={"code": _now(secret)}).status_code == 204
    other = Client(app)
    other.login("examcell", expect=401)                       # missing code
    other.login("examcell", mfa="123456", expect=401)         # wrong code
    other.login("examcell", mfa=_now(secret))


def _now(secret: str) -> str:
    import time

    return totp._code(secret, int(time.time() // 30))


@pytest.mark.parametrize("path", ["/api/docs", "/api/openapi.json"])
def test_docs_available_in_test_env(client, path):
    assert client.http.get(path).status_code == 200
