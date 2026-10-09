"""Direct tests for the last defensive branches (units where an HTTP journey would need heavy fixture set-up)."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.core.errors import Conflict, Invalid, NotFound
from app.models.accounts import UserAccount
from app.rbac.engine import load_principal
from app.resources.registry import build_registry


def principal_of(db, username):
    return load_principal(db, db.scalar(select(UserAccount).where(UserAccount.username == username)))


def test_attendance_default_weights_and_stale_corrections(db):
    from app.api.routers import attendance

    assert attendance.policy_weights(db, None, "PRESENT") == (Decimal(1), Decimal(1))
    assert attendance.policy_weights(db, None, "EXCUSED") == (Decimal(0), Decimal(0))
    assert attendance.policy_weights(db, None, "ABSENT") == (Decimal(0), Decimal(1))
    p = principal_of(db, "demoadmin")
    with pytest.raises(NotFound):
        attendance.apply_correction(db, p, SimpleNamespace(attendance_id=99999999, attendance_version=1, requested_status_id=1))
    row = db.execute(text("SELECT attendance_id, version FROM student_attendance LIMIT 1")).first()
    if row:
        with pytest.raises(Conflict):
            attendance.apply_correction(db, p, SimpleNamespace(attendance_id=row.attendance_id, attendance_version=row.version + 5, requested_status_id=1))


def test_attendance_summary_for_a_single_student(as_user, db):
    sec = db.execute(text("SELECT course_offering_section_id, student_id FROM student_attendance LIMIT 1")).first()
    if sec is None:
        pytest.skip("no attendance rows in the demo data")
    r = as_user("demoadmin").get(f"/attendance/summary?course_offering_section_id={sec[0]}&student_id={sec[1]}")
    assert r.status_code == 200 and len(r.json()["results"]) == 1


def test_announcement_delivery_for_every_audience(as_user, db):
    from app.resources.domain_hooks import deliver_announcement

    assert deliver_announcement(db, 99999999) == 0
    reg = as_user("registrar")
    atype = db.execute(text("SELECT announcement_type_id FROM announcement_type LIMIT 1")).scalar()
    aid = reg.post("/communication/announcement", json={"announcement_type_id": atype, "title": "Hello", "description": "x",
                                                        "publish_from": "2026-01-01T00:00:00Z", "audience_type": "CUSTOM"}).json()["announcement_id"]
    uid = db.execute(text("SELECT user_id FROM user_account WHERE username='student'")).scalar()
    pid = db.execute(text("SELECT programme_id FROM programme LIMIT 1")).scalar()
    assert reg.put(f"/communication/announcement/{aid}/targets", json={"user_ids": [uid], "programme_ids": [pid]}).status_code == 200
    for kind in ("CUSTOM", "PROGRAMME", "STUDENTS", "STAFF", "DEPARTMENT", "ALL"):
        db.execute(text("UPDATE announcement SET audience_type=:k WHERE announcement_id=:a"), {"k": kind, "a": aid})
        deliver_announcement(db, aid)
    queued = db.execute(text("SELECT count(*) FROM job WHERE kind='notify.users'")).scalar()
    assert queued >= 4


def test_activity_defaults_and_error_paths(db):
    from app.resources.activity import _owner, prepare_activity_create

    reg = build_registry()
    spec = reg["journal_publication"]
    admin = principal_of(db, "demoadmin")
    with pytest.raises(Invalid):
        prepare_activity_create(db, spec, admin, {})                     # no employee chosen and the admin is not one
    nobody = db.execute(text("SELECT employee_id FROM employee e WHERE NOT EXISTS (SELECT 1 FROM employee_assignment a WHERE a.employee_id=e.employee_id AND a.end_date IS NULL) LIMIT 1")).scalar()
    if nobody:
        with pytest.raises(Invalid):
            prepare_activity_create(db, spec, admin, {"employee_id": nobody})
    emp = db.execute(text("SELECT employee_id FROM employee_assignment WHERE end_date IS NULL LIMIT 1")).scalar()
    out = prepare_activity_create(db, spec, admin, {"employee_id": emp, "department_id": None})
    assert out["department_id"] is not None
    ghost = SimpleNamespace(employee_id=None, staff_activity_id=db.execute(text("SELECT staff_activity_id FROM staff_activity LIMIT 1")).scalar())
    assert isinstance(_owner(db, ghost), int)
    with pytest.raises(Invalid):
        db.execute(text("DELETE FROM activity_type WHERE activity_type_code='JOURNAL_PUBLICATION'"))
        prepare_activity_create(db, spec, admin, {"employee_id": emp})


def test_legacy_password_hash_is_upgraded_on_login(app, db):
    import base64
    import hashlib

    from tests.conftest import DEMO_PASSWORD, Client

    salt, iterations = "abc123", 600000
    digest = base64.b64encode(hashlib.pbkdf2_hmac("sha256", DEMO_PASSWORD.encode(), salt.encode(), iterations)).decode()
    db.execute(text("UPDATE user_account SET password_hash=:h WHERE username='teacher'"), {"h": f"pbkdf2_sha256${iterations}${salt}${digest}"})
    db.commit()
    Client(app).login("teacher")
    assert db.execute(text("SELECT password_hash FROM user_account WHERE username='teacher'")).scalar().startswith("$argon2")


def test_idempotency_key_in_flight_and_replay(as_user, db):
    c = as_user("demoadmin")
    h = {"Idempotency-Key": "abc-1", **c.csrf_headers()}
    path, body = None, None
    for g in c.get("/meta").json()["groups"]:
        for r in g["resources"]:
            if r["path"].startswith("reference/") and r["can"]["create"]:
                cols = c.get("/meta/" + r["path"]).json()["columns"]
                need = [x for x in cols if x["required"] and not x["readonly"]]
                if len(need) == 1 and need[0]["kind"] == "string":
                    path, body = "/" + r["path"], {need[0]["name"]: "Q9X"}
                    break
        if path:
            break
    if path is None:
        pytest.skip("no simple resource")
    first = c.http.post("/api/v1" + path, json=body, headers=h)
    second = c.http.post("/api/v1" + path, json=body, headers=h)
    if first.status_code != 201:
        pytest.skip(f"chosen resource needs more fields: {first.text[:120]}")
    assert second.status_code == 201 and second.json() == first.json()
    db.execute(text("INSERT INTO idempotency_key (key, user_id, route, request_digest, response_body, created_at) "
                    "SELECT 'stuck-1', user_id, '/api/v1/x', 'd', NULL, now() FROM user_account WHERE username='demoadmin'"))
    db.commit()
    r = c.http.post("/api/v1" + path, json=body, headers={"Idempotency-Key": "stuck-1", **c.csrf_headers()})
    assert r.status_code == 409
