"""Delegated administration: a super administrator creates organisations; each organisation admin creates and manages
the people of that organisation only."""
import pytest
from sqlalchemy import text

from tests.conftest import Client

ORG = {"code": "NEWU", "name": "New University College", "email": "info@newu.edu", "admin_username": "newu.admin",
       "admin_email": "admin@newu.edu", "admin_first_name": "Nina", "admin_last_name": "Owner"}


def login(app, username, password, portal="organisation"):
    c = Client(app)
    r = c.http.post("/api/v1/auth/login", json={"username": username, "password": password, "portal": portal},
                    headers={"X-CSRF-Token": c.csrf})
    assert r.status_code == 200, r.text
    c.http.headers["Authorization"] = "Bearer " + r.json()["access"]
    return c


def first_sign_in(app, username, temp, portal="organisation", new="Brand#New2026pw"):
    """A new account must replace its temporary password before doing anything else."""
    c = login(app, username, temp, portal)
    assert c.post("/auth/change-password", json={"current_password": temp, "new_password": new}).status_code in (200, 204)
    return login(app, username, new, portal)


@pytest.fixture()
def org(as_user, app, db):
    created = as_user("demoadmin").post("/security/organisations", json=ORG)
    assert created.status_code == 201, created.text
    body = created.json()
    pw = body["administrator"]["temporary_password"]
    return body, first_sign_in(app, "newu.admin", pw), "Brand#New2026pw"


def test_super_admin_creates_an_organisation_with_its_administrator(as_user, app, db):
    sa = as_user("demoadmin")
    r = sa.post("/security/organisations", json=ORG)
    assert r.status_code == 201
    body = r.json()
    assert body["institution"]["code"] == "NEWU" and body["administrator"]["username"] == "newu.admin"
    assert len(body["administrator"]["temporary_password"]) >= 14
    assert sa.post("/security/organisations", json=ORG).status_code == 409                                  # duplicate username
    assert sa.post("/security/organisations", json={**ORG, "admin_username": "other.admin"}).status_code == 409  # duplicate code
    me = login(app, "newu.admin", body["administrator"]["temporary_password"]).get("/auth/me").json()
    assert me["roles"] == ["INSTITUTION_ADMIN"] and me["must_change_password"] is True
    listed = {o["institution_code"]: o for o in sa.get("/security/organisations").json()["results"]}
    assert listed["NEWU"]["administrators"] == ["newu.admin"]


def test_only_super_administrators_create_organisations(as_user):
    assert as_user("registrar").post("/security/organisations", json=ORG).status_code == 403
    assert as_user("student").post("/security/organisations", json=ORG).status_code == 403


def test_organisation_admin_builds_the_team_below_them(org):
    _, admin, _ = org
    team = {"registrar": "REGISTRAR", "examiner": "CONTROLLER_EXAMINATIONS", "helpdesk": "GRIEVANCE_OFFICER",
            "teacher": "FACULTY", "head": "HEAD_DEPARTMENT"}
    for username, role in team.items():
        scope = {"scope_type": "DEPARTMENT", "scope_id": 1} if role in ("FACULTY", "HEAD_DEPARTMENT") else {}
        r = admin.post("/security/users", json={"username": f"newu.{username}", "email": f"{username}@newu.edu", "role_code": role, **scope})
        if scope:
            assert r.status_code == 403            # department 1 belongs to the demo institution, not this one
            continue
        assert r.status_code == 201, r.text
        assert r.json()["temporary_password"]
    users = admin.get("/security/users").json()["results"]
    assert {u["username"] for u in users} == {"newu.admin", "newu.registrar", "newu.examiner", "newu.helpdesk"}
    assert all(u["roles"] for u in users)
    roles = {x["role_code"] for x in admin.get("/security/roles").json()["results"]}
    assert "REGISTRAR" in roles and not roles & {"SUPER_ADMIN", "INSTITUTION_ADMIN", "SYSTEM_ADMIN"}


def test_organisation_admin_cannot_escalate_or_reach_other_organisations(org, db):
    body, admin, _ = org
    mine = body["institution"]["institution_id"]
    for role, scope in (("SUPER_ADMIN", "GLOBAL"), ("INSTITUTION_ADMIN", "INSTITUTION"), ("SYSTEM_ADMIN", "GLOBAL")):
        r = admin.post("/security/users", json={"username": f"x.{role.lower()}", "email": "x@newu.edu", "role_code": role,
                                                "scope_type": scope, **({"scope_id": mine} if scope == "INSTITUTION" else {})})
        assert r.status_code in (403, 422), (role, r.text)
    assert admin.post("/security/users", json={"username": "sneaky", "email": "s@x.org", "institution_id": 1}).status_code == 403
    mine_user = admin.post("/security/users", json={"username": "newu.t", "email": "t@newu.edu"}).json()["user_id"]
    r = admin.post("/security/role-assignments", json={"user_id": mine_user, "role_code": "REGISTRAR", "scope_type": "INSTITUTION", "scope_id": 1})
    assert r.status_code == 403
    demo_user = db.execute(text("SELECT user_id FROM user_account WHERE username='student'")).scalar()
    assert admin.get(f"/security/users/{demo_user}").status_code == 404
    assert admin.post(f"/security/users/{demo_user}/reset-password").status_code == 404
    assert admin.patch(f"/security/users/{demo_user}", json={"is_active": False}).status_code == 404
    assert admin.post("/security/role-assignments", json={"user_id": demo_user, "role_code": "STUDENT", "scope_type": "SELF"}).status_code == 404
    super_id = db.execute(text("SELECT user_id FROM user_account WHERE username='demoadmin'")).scalar()
    assert admin.get(f"/security/users/{super_id}").status_code == 404
    names = {u["username"] for u in admin.get("/security/users?page_size=100").json()["results"]}
    assert "student" not in names and "demoadmin" not in names and "newu.t" in names
    assert admin.get("/ops/jobs").status_code == 403 and admin.get("/ops/overview").status_code == 403
    orgs = admin.get("/security/organisations").json()["results"]
    assert [o["institution_id"] for o in orgs] == [mine]
    assert admin.put("/security/roles/1/permissions", json={"permissions": []}).status_code == 403


def test_people_data_stays_inside_the_organisation(org):
    _, admin, _ = org
    assert admin.get("/people/student").json()["count"] == 0
    assert admin.get("/people/employee").json()["count"] == 0
    pages = {r["path"] for g in admin.get("/meta").json()["groups"] for r in g["resources"]}
    assert "people/student" in pages and not any(p.startswith(("security/", "accounts/", "tenancy/")) for p in pages)


def test_organisation_admins_use_their_own_portal_only(org, app):
    _, _, pw = org
    c = Client(app)
    r = c.http.post("/api/v1/auth/login", json={"username": "newu.admin", "password": pw, "portal": "admin"},
                    headers={"X-CSRF-Token": c.csrf})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_portal"


def test_students_get_logins_from_their_organisation_admin(as_user, app):
    created = as_user("demoadmin").post("/security/organisations", json={**ORG, "code": "TWOU", "admin_username": "twou.admin", "admin_email": "a@twou.edu"}).json()
    admin = first_sign_in(app, "twou.admin", created["administrator"]["temporary_password"])
    made = admin.post("/security/users", json={"username": "twou.student", "email": "s@twou.edu", "role_code": "STUDENT",
                                               "scope_type": "SELF", "password": "Student#Pass2026x"})
    assert made.status_code == 201, made.text
    student = first_sign_in(app, "twou.student", "Student#Pass2026x", portal="student")
    assert student.get("/auth/me").json()["roles"] == ["STUDENT"]


def test_demo_organisation_admin_can_sign_in_and_see_only_their_people(app):
    c = login(app, "orgadmin", "Campus@2026")
    names = {u["username"] for u in c.get("/security/users?page_size=100").json()["results"]}
    assert {"student", "teacher", "registrar", "orgadmin"} <= names and "demoadmin" not in names
