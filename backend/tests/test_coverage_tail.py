"""Remaining defensive branches: file integrity, identifier validation, scoped 404s and client edge cases."""
import io

import pytest
from pypdf import PdfWriter
from sqlalchemy import text

from tests.test_files import pdf_bytes, png_bytes, upload


def test_upload_content_validation_branches(as_user):
    c = as_user("student")
    w = PdfWriter()
    w.add_blank_page(72, 72)
    w.encrypt("secret")
    buf = io.BytesIO()
    w.write(buf)
    assert "Encrypted" in upload(c, "locked.pdf", buf.getvalue()).text
    assert "damaged" in upload(c, "broken.pdf", b"%PDF-1.4 garbage that is not a pdf").text
    assert "JPEG" in upload(c, "x.jpg", png_bytes()).text
    assert "damaged" in upload(c, "x.png", b"\x89PNG\r\n\x1a\n" + b"junk").text
    assert c.http.post("/api/v1/files", files={"file": ("a.pdf", pdf_bytes())}, data={"confidentiality": "TOPSECRET"}).status_code == 422


def test_download_detects_missing_and_tampered_storage(as_user, db):
    from app.storage import get_storage

    c = as_user("student")
    fid = upload(c, "doc.pdf", pdf_bytes()).json()["file_object_id"]
    key = db.execute(text("SELECT storage_key FROM file_object WHERE file_object_id=:i"), {"i": fid}).scalar()
    store = get_storage()
    original = store.get(key)
    store.put(key, original + b"tamper", "application/pdf")
    r = c.http.get(f"/api/v1/files/{fid}")
    assert r.status_code == 500 and r.json()["error"]["code"] == "integrity_failure"
    store.delete(key)
    assert c.http.get(f"/api/v1/files/{fid}").status_code == 404


def test_identifier_validation_and_scope(as_user, db):
    admin = as_user("demoadmin")
    ids = [e for (e,) in db.execute(text("SELECT employee_id FROM employee ORDER BY employee_id LIMIT 2"))]
    a, b = ids[0], ids[1]
    assert admin.put(f"/hr/secure/employees/{a}/pan", json={"pan_number": "1234567890", "name_as_per_pan": "A"}).status_code == 422
    assert admin.put(f"/hr/secure/employees/{a}/pan", json={"pan_number": "ABCPE1234F", "name_as_per_pan": "A"}).status_code == 200
    assert admin.put(f"/hr/secure/employees/{b}/pan", json={"pan_number": "ABCPE1234F", "name_as_per_pan": "B"}).status_code == 409
    body = {"account_holder_name": "A", "bank_name": "SBI", "account_number": "12345abcde", "ifsc_code": "SBIN0001234"}
    assert admin.post(f"/hr/secure/employees/{a}/bank-accounts", json=body).status_code == 422
    assert admin.post(f"/hr/secure/employees/{a}/bank-accounts", json={**body, "account_number": "123456789012", "ifsc_code": "SBIN1001234"}).status_code == 422
    assert admin.put("/hr/secure/employees/99999999/pan", json={"pan_number": "ABCPE1234F", "name_as_per_pan": "A"}).status_code == 404
    from app.rbac.engine import Grant
    assert Grant


def test_ai_client_disabled_and_non_json_reply(monkeypatch):
    import httpx2 as httpx

    from app.ai import client
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_enabled", False)
    with pytest.raises(client.AIDisabled):
        client.chat("s", "u")
    monkeypatch.setattr(get_settings(), "ai_enabled", True)
    monkeypatch.setattr(get_settings(), "ai_api_key", "k")
    client.set_transport(httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "{not json}"}}]})))
    try:
        with pytest.raises(client.AIUnavailable):
            client.chat_json("s", "u")
    finally:
        client.set_transport(None)


def test_out_of_range_values_are_client_errors_not_500s(as_user):
    c = as_user("demoadmin")
    assert c.get("/hr/awarding-body-type/32768").status_code in (404, 422)
    r = c.get("/hr/awarding-body-type?awarding_body_type_id=99999999999")
    assert r.status_code in (200, 422)


def test_student_dashboard_hides_organisation_wide_counters(as_user):
    labels = {t["label"] for t in as_user("student").get("/dashboard").json()["tiles"]}
    assert "Applicants" not in labels and "Attendance corrections pending" not in labels
    assert "Applicants" in {t["label"] for t in as_user("registrar").get("/dashboard").json()["tiles"]}


def _pages(client):
    return {r["path"] for g in client.get("/meta").json()["groups"] for r in g["resources"]}


def test_navigation_lists_only_pages_the_role_can_really_use(as_user):
    student = _pages(as_user("student"))
    assert "people/student" in student and "support/grievance" in student
    assert not any(p.startswith(("reference/", "organization/", "curriculum/course-catalog", "admissions/admission-category")) for p in student)
    assert "people/employee" not in student and "hr/employee-aadhaar" not in student
    registrar = _pages(as_user("registrar"))
    assert "reference/country" in registrar and "people/student" in registrar
    assert "reference/country" not in _pages(as_user("hod"))


PORTAL_OF = {"student": "student", "student2": "student", "teacher": "faculty", "hod": "leadership", "campusadm": "leadership",
             "registrar": "office", "examcell": "exam", "support": "support", "demoadmin": "admin", "orgadmin": "organisation"}


@pytest.mark.parametrize("username,portal", sorted(PORTAL_OF.items()))
def test_each_account_signs_in_only_through_its_own_portal(app, username, portal):
    from tests.conftest import DEMO_PASSWORD, Client

    ok = Client(app)
    assert ok.http.post("/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD, "portal": portal},
                        headers={"X-CSRF-Token": ok.csrf}).status_code == 200
    other = next(p for p in ("student", "faculty", "leadership", "office", "exam", "support", "organisation", "admin") if p != portal)
    bad = Client(app)
    r = bad.http.post("/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD, "portal": other},
                      headers={"X-CSRF-Token": bad.csrf})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_portal" and "Authorization" not in bad.http.headers
    assert bad.http.get("/api/v1/auth/me").status_code == 401        # no session was created


def test_portal_is_optional_and_validated(app):
    from tests.conftest import DEMO_PASSWORD, Client

    c = Client(app)
    assert c.http.post("/api/v1/auth/login", json={"username": "student", "password": DEMO_PASSWORD, "portal": "nonsense"},
                       headers={"X-CSRF-Token": c.csrf}).status_code == 422
    c.login("student")                                               # API clients without a portal still work


def test_owner_overview_is_for_super_administrators_only(as_user):
    assert as_user("student").get("/ops/overview").status_code == 403
    assert as_user("registrar").get("/ops/overview").status_code == 403
    r = as_user("demoadmin").get("/ops/overview")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["people"]["students"] >= 1 and d["users"]["super_admins"] >= 1 and d["system"]["database"] == "connected"
    assert {"users_by_role", "recent_audit", "recent_logins", "jobs", "workflow", "sessions", "logins_24h"} <= set(d)
    assert "password" not in str(d).lower().replace("must_change_password", "")
