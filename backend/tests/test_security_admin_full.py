"""Every guard rail of the identity-and-access administration API, including a delegated (non-super) administrator."""
import pytest
from sqlalchemy import text

from app.core.security import hash_password
from tests.conftest import DEMO_PASSWORD, Client


@pytest.fixture()
def delegate(app, db):
    """An institution-level administrator who is NOT a super administrator and holds only some permissions."""
    role_id = db.execute(text(
        "INSERT INTO role (role_code, role_name, role_category, role_level, is_system_role, is_assignable, is_active) "
        "VALUES ('DELEGATE_ADMIN', 'Delegated administrator', 'ADMINISTRATIVE', 'INSTITUTION', false, true, true) RETURNING role_id")).scalar()
    for act in ("READ", "CREATE", "UPDATE", "ASSIGN", "CONFIGURE"):
        db.execute(text("INSERT INTO role_permission (role_id, permission_id, permission_effect) "
                        "SELECT :r, permission_id, 'ALLOW' FROM permission WHERE permission_code = :c"), {"r": role_id, "c": f"IAM.ALL.{act}"})
    uid = db.execute(text(
        "INSERT INTO user_account (username, email, password_hash, account_status, is_active) VALUES ('delegate', 'd@example.org', :p, 'ACTIVE', true) RETURNING user_id"),
        {"p": hash_password(DEMO_PASSWORD)}).scalar()
    db.execute(text("INSERT INTO user_role_assignment (user_id, role_id, scope_type, institution_id, valid_from, assignment_status) "
                    "VALUES (:u, :r, 'INSTITUTION', 1, now(), 'ACTIVE')"), {"u": uid, "r": role_id})
    db.commit()
    c = Client(app)
    c.login("delegate")
    return c


def uid_of(db, username):
    return db.execute(text("SELECT user_id FROM user_account WHERE username=:u"), {"u": username}).scalar()


def test_user_listing_search_and_paging(as_user):
    a = as_user("demoadmin")
    everyone = a.get("/security/users?page_size=3").json()
    assert everyone["count"] >= 9 and len(everyone["results"]) == 3 and everyone["next"] == 2
    assert a.get("/security/users?page_size=3&page=2").json()["previous"] == 1
    hits = a.get("/security/users?search=regis").json()["results"]
    assert hits and all("regis" in (u["username"] + u["email"]).lower() for u in hits)
    assert a.get("/security/users?search=%25_").status_code == 200
    assert "password_hash" not in str(everyone) and "mfa_secret" not in str(everyone)


def test_unknown_user_ids_are_404_everywhere(as_user):
    a = as_user("demoadmin")
    assert a.get("/security/users/999999").status_code == 404
    assert a.patch("/security/users/999999", json={"first_name": "x"}).status_code == 404
    for path in ("reset-password", "unlock", "revoke-sessions"):
        assert a.post(f"/security/users/999999/{path}").status_code == 404
    assert a.post("/security/users/999999/link-person", json={"student_id": 1}).status_code == 404


def test_admin_user_lifecycle(as_user, db, app):
    a = as_user("demoadmin")
    u = a.post("/security/users", json={"username": "life.cycle", "email": "lc@example.org", "password": "Strong#Pass2026x"}).json()
    assert "temporary_password" not in u                                     # caller chose the password
    uid = u["user_id"]
    assert a.get(f"/security/users/{uid}").json()["username"] == "life.cycle"
    assert a.patch(f"/security/users/{uid}", json={"first_name": "Life", "email": "life@example.org"}).json()["first_name"] == "Life"
    assert a.post("/security/users", json={"username": "bad name!", "email": "x@example.org"}).status_code == 422
    assert a.post("/security/users", json={"username": "weak.pw", "email": "x@example.org", "password": "short"}).status_code == 422
    assert a.post(f"/security/users/{uid}/unlock").status_code == 204
    pw = a.post(f"/security/users/{uid}/reset-password").json()["temporary_password"]
    c = Client(app)
    c.login("life.cycle", pw)
    assert a.post(f"/security/users/{uid}/revoke-sessions").status_code == 204 and c.get("/auth/me").status_code == 401
    assert a.patch(f"/security/users/{uid}", json={"is_active": False}).json()["account_status"] == "DISABLED"
    assert a.patch(f"/security/users/{uid}", json={"is_active": True}).json()["account_status"] == "ACTIVE"
    me = a.get("/auth/me").json()["user_id"]
    assert a.patch(f"/security/users/{me}", json={"is_active": False}).status_code == 422


def test_delegated_admin_cannot_touch_super_administrators(delegate, db):
    """Platform owners are invisible to organisation-level administrators (404, not 403)."""
    boss = uid_of(db, "demoadmin")
    for call in (delegate.patch(f"/security/users/{boss}", json={"first_name": "x"}), delegate.post(f"/security/users/{boss}/reset-password"),
                 delegate.post(f"/security/users/{boss}/unlock"), delegate.post(f"/security/users/{boss}/revoke-sessions"),
                 delegate.post(f"/security/users/{boss}/link-person", json={"student_id": 1}),
                 delegate.post("/security/role-assignments", json={"user_id": boss, "role_code": "REGISTRAR", "scope_type": "INSTITUTION", "scope_id": 1})):
        assert call.status_code == 404, call.text


def test_link_person_rules(as_user, db):
    a = as_user("demoadmin")
    uid = a.post("/security/users", json={"username": "link.me", "email": "lm@example.org"}).json()["user_id"]
    assert a.post(f"/security/users/{uid}/link-person", json={"student_id": 99999999}).status_code == 404
    free = db.execute(text("SELECT student_id FROM student s WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.student_id = s.student_id) LIMIT 1")).scalar()
    assert a.post(f"/security/users/{uid}/link-person", json={"student_id": free}).status_code == 204
    other_free = db.execute(text("SELECT student_id FROM student s WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.student_id = s.student_id) LIMIT 1")).scalar()
    assert a.post(f"/security/users/{uid}/link-person", json={"student_id": other_free}).status_code == 409      # user already has a student
    both = a.post(f"/security/users/{uid}/link-person", json={"student_id": 1, "employee_id": 1})
    assert both.status_code == 422


def test_role_catalogue_and_permission_editing(as_user, db, delegate):
    a = as_user("demoadmin")
    roles = a.get("/security/roles").json()["results"]
    assert any(r["role_code"] == "REGISTRAR" for r in roles)
    rid = next(r["role_id"] for r in roles if r["role_code"] == "DELEGATE_ADMIN")
    detail = a.get(f"/security/roles/{rid}").json()
    assert {p["code"] for p in detail["permissions"]} >= {"IAM.ALL.READ", "IAM.ALL.ASSIGN"}
    assert a.get("/security/roles/999999").status_code == 404
    assert a.get("/security/permissions?module=admission").json()["results"]
    assert len(a.get("/security/permissions").json()["results"]) > 500
    # superuser edits a custom role
    assert a.put(f"/security/roles/{rid}/permissions", json={"allow": ["IAM.ALL.READ", "IAM.ALL.ASSIGN"], "deny": ["IAM.ALL.DELETE"]}).status_code == 204
    assert {(p["code"], p["effect"]) for p in a.get(f"/security/roles/{rid}").json()["permissions"]} == {
        ("IAM.ALL.READ", "ALLOW"), ("IAM.ALL.ASSIGN", "ALLOW"), ("IAM.ALL.DELETE", "DENY")}
    assert a.put(f"/security/roles/{rid}/permissions", json={"allow": ["NOT.A.PERMISSION"]}).status_code == 422
    assert a.put("/security/roles/999999/permissions", json={"allow": []}).status_code == 404
    sa_id = next(r["role_id"] for r in roles if r["role_code"] == "SUPER_ADMIN")
    assert a.put(f"/security/roles/{sa_id}/permissions", json={"allow": []}).status_code == 422


def test_delegated_admin_cannot_escalate_through_roles(delegate, db):
    roles = {r["role_code"]: r["role_id"] for r in delegate.get("/security/roles").json()["results"]}
    assert "SYSTEM_ADMIN" not in roles                       # privileged roles are not even listed to a delegate
    roles["SYSTEM_ADMIN"] = db.execute(text("SELECT role_id FROM role WHERE role_code='SYSTEM_ADMIN'")).scalar()
    assert delegate.put(f"/security/roles/{roles['SYSTEM_ADMIN']}/permissions", json={"allow": []}).status_code == 403
    r = delegate.put(f"/security/roles/{roles['DELEGATE_ADMIN']}/permissions", json={"allow": ["ADMISSION.ALL.APPROVE"]})
    assert r.status_code == 403 and "do not hold" in r.json()["error"]["message"]
    assert delegate.put(f"/security/roles/{roles['DELEGATE_ADMIN']}/permissions", json={"allow": ["IAM.ALL.READ"]}).status_code == 204


def test_assignment_rules(as_user, delegate, db):
    a = as_user("demoadmin")
    uid = a.post("/security/users", json={"username": "assign.target", "email": "at@example.org"}).json()["user_id"]
    db.execute(text("UPDATE user_account SET institution_id = 1 WHERE user_id = :u"), {"u": uid})
    db.commit()
    body = {"user_id": uid, "role_code": "REGISTRAR", "scope_type": "INSTITUTION", "scope_id": 1}
    assert a.post("/security/role-assignments", json={**body, "user_id": 99999999}).status_code == 404
    assert a.post("/security/role-assignments", json={**body, "role_code": "NO_SUCH_ROLE"}).status_code == 404
    assert a.post("/security/role-assignments", json={**body, "scope_id": None, "scope_type": "GLOBAL", "role_code": "SYSTEM_ADMIN"}).status_code == 201
    assert a.post("/security/role-assignments", json={**body, "scope_type": "GLOBAL", "scope_id": 5, "role_code": "SYSTEM_ADMIN"}).status_code == 422
    db.execute(text("UPDATE role SET is_assignable = false WHERE role_code = 'FINANCE_OFFICER'"))
    db.commit()
    assert a.post("/security/role-assignments", json={**body, "role_code": "FINANCE_OFFICER"}).status_code == 422
    # delegate: privileged role, global scope, other organisation, permissions it does not hold
    assert delegate.post("/security/role-assignments", json={**body, "role_code": "SYSTEM_ADMIN", "scope_type": "GLOBAL", "scope_id": None}).status_code == 403
    assert delegate.post("/security/role-assignments", json={**body, "scope_id": 2}).status_code == 403
    assert delegate.post("/security/role-assignments", json=body).status_code == 403   # target holds a platform role: off limits
    uid2 = a.post("/security/users", json={"username": "assign.target2", "email": "at2@example.org"}).json()["user_id"]
    db.execute(text("UPDATE user_account SET institution_id = 1 WHERE user_id = :u"), {"u": uid2})
    db.commit()
    body2 = {**body, "user_id": uid2}
    r = delegate.post("/security/role-assignments", json=body2)
    assert r.status_code == 403 and "do not hold" in r.json()["error"]["message"]
    # a role the delegate fully covers can be assigned at its own institution
    db.execute(text("INSERT INTO role (role_code, role_name, role_category, role_level, is_assignable, is_active) VALUES ('READER', 'Reader', 'AUDIT', 'INSTITUTION', true, true)"))
    db.execute(text("INSERT INTO role_permission (role_id, permission_id, permission_effect) SELECT r.role_id, p.permission_id, 'ALLOW' FROM role r, permission p WHERE r.role_code='READER' AND p.permission_code='IAM.ALL.READ'"))
    db.commit()
    ok = delegate.post("/security/role-assignments", json={**body2, "role_code": "READER"})
    assert ok.status_code == 201
    # revoke rules
    aid = ok.json()["assignment_id"]
    assert delegate.delete(f"/security/role-assignments/{aid}").status_code == 204
    assert delegate.delete(f"/security/role-assignments/{aid}").status_code == 404
    sysrole = a.get(f"/security/users/{uid}").json()["roles"][0]["assignment_id"]
    assert delegate.delete(f"/security/role-assignments/{sysrole}").status_code == 403
    me = a.get("/auth/me").json()["user_id"]
    own = next(x for x in a.get(f"/security/users/{me}").json()["roles"] if x["role_code"] == "SUPER_ADMIN")["assignment_id"] if any(
        x["role_code"] == "SUPER_ADMIN" for x in a.get(f"/security/users/{me}").json()["roles"]) else None
    if own:
        assert a.delete(f"/security/role-assignments/{own}").status_code == 422
    assert a.delete("/security/role-assignments/99999999").status_code == 404


def test_auto_staff_self_on_teaching_roles(as_user, db):
    a = as_user("demoadmin")
    uid = a.post("/security/users", json={"username": "auto.self", "email": "as@example.org"}).json()["user_id"]
    assert a.post("/security/role-assignments", json={"user_id": uid, "role_code": "FACULTY", "scope_type": "DEPARTMENT", "scope_id": 1}).status_code == 201
    roles = {r["role_code"] for r in a.get(f"/security/users/{uid}").json()["roles"]}
    assert {"FACULTY", "STAFF_SELF"} <= roles


def test_audit_is_limited_for_delegated_admins(as_user, delegate):
    as_user("demoadmin").post("/reference/gender", json={"gender_code": "AUD2", "gender_name": "Audit two"})
    assert delegate.get("/security/audit").status_code == 403          # no AUDIT permission at all
    admin = as_user("demoadmin")
    assert admin.get("/security/audit?resource=gender&action=create&module=REFERENCE&record_id=1&actor=1").status_code == 200
    campus = as_user("campusadm")
    assert campus.get("/security/audit").status_code in (200, 403)
