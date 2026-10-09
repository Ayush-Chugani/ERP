"""Administration APIs: users, role assignment guard rails, audit trail, dashboard, notifications, jobs."""
from tests.conftest import Client


def test_admin_creates_user_and_user_must_change_password(as_user, app):
    admin = as_user("demoadmin")
    r = admin.post("/security/users", json={"username": "new.staff", "email": "new.staff@example.org",
                                            "first_name": "New", "last_name": "Staff"})
    assert r.status_code == 201, r.text
    temp = r.json()["temporary_password"]
    c = Client(app)
    c.login("new.staff", temp)
    assert c.get("/auth/me").json()["must_change_password"] is True
    assert c.get("/people/student").status_code == 403           # blocked until the password is changed
    r = c.post("/auth/change-password", json={"current_password": temp, "new_password": "Brand#New2026pw"})
    assert r.status_code == 200
    c.http.headers["Authorization"] = "Bearer " + r.json()["access"]   # the old session was rotated away
    assert c.get("/auth/me").json()["must_change_password"] is False
    assert admin.post("/security/users", json={"username": "NEW.staff", "email": "x@example.org"}).status_code == 409


def test_users_endpoint_is_admin_only(as_user):
    for u in ("student", "teacher", "hod", "registrar"):
        assert as_user(u).get("/security/users").status_code == 403


def test_assignment_guard_rails(as_user):
    admin = as_user("demoadmin")
    uid = admin.post("/security/users", json={"username": "guard.test", "email": "g@example.org"}).json()["user_id"]
    # super-admin can assign scoped roles
    r = admin.post("/security/role-assignments", json={"user_id": uid, "role_code": "REGISTRAR",
                                                         "scope_type": "INSTITUTION", "scope_id": 1})
    assert r.status_code == 201, r.text
    # wrong level is rejected, as is a missing scope id
    assert admin.post("/security/role-assignments", json={"user_id": uid, "role_code": "REGISTRAR",
                                                            "scope_type": "CAMPUS", "scope_id": 1}).status_code == 422
    assert admin.post("/security/role-assignments", json={"user_id": uid, "role_code": "REGISTRAR",
                                                            "scope_type": "INSTITUTION"}).status_code == 422
    # a registrar can never hand out privileged roles
    reg = as_user("registrar")
    assert reg.post("/security/role-assignments", json={"user_id": uid, "role_code": "SUPER_ADMIN",
                                                          "scope_type": "GLOBAL"}).status_code in (403,)
    me = admin.get("/auth/me").json()
    sa = next(a for a in admin.get(f"/security/users/{me['user_id']}").json()["roles"] if a["role_code"] == "SUPER_ADMIN") \
        if any(a["role_code"] == "SUPER_ADMIN" for a in admin.get(f"/security/users/{me['user_id']}").json()["roles"]) else None
    if sa:
        assert admin.delete(f"/security/role-assignments/{sa['assignment_id']}").status_code == 422


def test_role_change_takes_effect_for_the_user(as_user, app):
    admin = as_user("demoadmin")
    temp = admin.post("/security/users", json={"username": "fresh.reg", "email": "f@example.org"}).json()
    c = Client(app)
    c.login("fresh.reg", temp["temporary_password"])
    r = c.post("/auth/change-password", json={"current_password": temp["temporary_password"], "new_password": "Brand#New2026pw"})
    c.http.headers["Authorization"] = "Bearer " + r.json()["access"]
    assert c.get("/people/student").status_code == 403
    aid = admin.post("/security/role-assignments", json={"user_id": temp["user_id"], "role_code": "REGISTRAR",
                                                           "scope_type": "INSTITUTION", "scope_id": 1}).json()["assignment_id"]
    assert c.get("/people/student").status_code == 200
    assert admin.delete(f"/security/role-assignments/{aid}").status_code == 204
    assert c.get("/people/student").status_code == 403


def test_disabling_a_user_kills_their_sessions(as_user, app):
    admin = as_user("demoadmin")
    victim = Client(app)
    victim.login("support")
    uid = victim.get("/auth/me").json()["user_id"]
    assert admin.patch(f"/security/users/{uid}", json={"is_active": False}).status_code == 200
    assert victim.get("/auth/me").status_code == 401
    victim.login("support", expect=401)


def test_audit_trail_is_readable_by_auditors_only(as_user):
    admin = as_user("demoadmin")
    admin.post("/reference/gender", json={"gender_code": "AUD", "gender_name": "Audit"})
    rows = admin.get("/security/audit?resource=gender").json()["results"]
    assert rows and rows[0]["action"] == "create"
    assert as_user("student").get("/security/audit").status_code == 403


def test_dashboard_is_scope_aware(as_user):
    reg = {t["label"]: t["value"] for t in as_user("registrar").get("/dashboard").json()["tiles"]}
    st = as_user("student").get("/dashboard").json()["tiles"]
    assert reg["Active students"] > 0
    assert all(t["label"] != "Active staff" for t in st)


def test_notifications_roundtrip(as_user, db):
    from app.worker.queue import enqueue
    from app.worker.runner import run_one

    c = as_user("student")
    uid = c.get("/auth/me").json()["user_id"]
    enqueue(db, "notify.user", {"user_id": uid, "title": "Hello", "body": "World"})
    db.commit()
    assert run_one("test-worker", ["default"])
    items = c.get("/notifications?unread=true").json()
    assert items["count"] == 1
    nid = items["results"][0]["notification_id"]
    assert c.post(f"/notifications/{nid}/read").status_code == 204
    assert c.get("/notifications?unread=true").json()["count"] == 0
    assert c.get("/dashboard").json()["unread_notifications"] == 0


def test_link_person_and_announcement_targets(as_user, db):
    from sqlalchemy import text

    admin = as_user("demoadmin")
    uid = admin.post("/security/users", json={"username": "linked.staff", "email": "l@example.org"}).json()["user_id"]
    unlinked = db.execute(text("SELECT employee_id FROM employee e WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.employee_id = e.employee_id) LIMIT 1")).scalar()
    assert admin.post(f"/security/users/{uid}/link-person", json={}).status_code == 422
    assert admin.post(f"/security/users/{uid}/link-person", json={"employee_id": unlinked}).status_code == 204
    assert admin.post(f"/security/users/{uid}/link-person", json={"employee_id": unlinked}).status_code == 409
    assert db.execute(text("SELECT count(*) FROM user_role_assignment a JOIN role r USING (role_id) WHERE a.user_id=:u AND r.role_code='STAFF_SELF'"), {"u": uid}).scalar() == 1
    reg = as_user("registrar")
    atype = db.execute(text("SELECT announcement_type_id FROM announcement_type LIMIT 1")).scalar()
    aid = reg.post("/communication/announcement", json={"announcement_type_id": atype, "title": "Targeted", "description": "x",
                                                        "publish_from": "2026-01-01T00:00:00Z", "audience_type": "CUSTOM"}).json()["announcement_id"]
    assert reg.put(f"/communication/announcement/{aid}/targets", json={"user_ids": [uid], "programme_ids": []}).json()["user_ids"] == [uid]
    reg.post(f"/communication/announcement/{aid}/actions/submit")
    assert reg.put(f"/communication/announcement/{aid}/targets", json={"user_ids": []}).status_code == 409
