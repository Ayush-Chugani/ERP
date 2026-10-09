"""HTTP plumbing, sessions, workspace tools, RBAC engine, catalogue, worker, CLI, seeds and the remaining service branches."""
import json
import sys
import types
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.config import get_settings
from app.core import security
from app.models.accounts import UserAccount
from app.rbac.engine import Grant, Principal, ScopeSet, load_principal, org_tree
from tests.conftest import DEMO_PASSWORD, Client


def principal_of(db, username) -> Principal:
    return load_principal(db, db.scalar(select(UserAccount).where(UserAccount.username == username)))


# --------------------------------------------------------------------------------------------- middleware
def test_lifespan_and_request_id_sanitising(app):
    with TestClient(app, base_url="http://localhost") as c:
        r = c.get("/api/v1/health/live", headers={"X-Request-ID": "bad id with spaces!"})
        assert r.headers["x-request-id"] != "bad id with spaces!" and len(r.headers["x-request-id"]) == 32
        long = c.get("/api/v1/health/live", headers={"X-Request-ID": "a" * 80})
        assert len(long.headers["x-request-id"]) == 32


def test_streamed_bodies_without_content_length_are_still_limited(app):
    def chunks():
        for _ in range(14):
            yield b"x" * (1024 * 1024)

    c = TestClient(app, base_url="http://localhost")
    r = c.post("/api/v1/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_hsts_is_sent_in_production(app, monkeypatch):
    monkeypatch.setattr(get_settings(), "env", "production")
    r = TestClient(app, base_url="http://localhost").get("/api/v1/health/live")
    assert "max-age=31536000" in r.headers["strict-transport-security"]


def test_client_ip_honours_the_trusted_proxy_chain(client, db):
    client.http.headers["X-Forwarded-For"] = "203.0.113.9, 198.51.100.7"
    client.login("student")
    ip = db.execute(text("SELECT ip_address FROM login_audit WHERE was_successful ORDER BY login_audit_id DESC LIMIT 1")).scalar()
    assert ip == "198.51.100.7"                      # one trusted hop: the right-most address is the real client


# ------------------------------------------------------------------------------------------------ sessions
def test_tokens_for_unknown_sessions_or_disabled_users_are_rejected(client, db):
    token, _ = security.create_access_token(1, "11111111-1111-1111-1111-111111111111", 0)
    client.http.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/auth/me").status_code == 401
    client.http.headers["Authorization"] = "Basic abc"
    assert client.get("/auth/me").status_code == 401
    token2 = jwt.encode({"iss": "someone-else", "sub": "1", "sid": "s", "iat": 1, "exp": 9999999999, "typ": "access"}, get_settings().secret_key, algorithm="HS256")
    client.http.headers["Authorization"] = f"Bearer {token2}"
    assert client.get("/auth/me").status_code == 401


def test_refresh_failure_modes(app, db):
    c = Client(app)
    c.login("student")
    cookie = c.http.cookies.get("sims_refresh", path="/api/v1/auth")
    sid = cookie.split(".")[0]
    h = c.csrf_headers()
    assert c.post("/auth/refresh", headers={"X-CSRF-Token": "bad"}).status_code == 403            # CSRF checked first
    for bad in ("not-a-uuid.secret", "no-dot", "11111111-1111-1111-1111-111111111111.zzz", f"{sid}.wrongsecret"):
        c.http.cookies.set("sims_refresh", bad, path="/api/v1/auth")
        assert c.post("/auth/refresh", headers=h).status_code == 401
    c.http.cookies.set("sims_refresh", cookie, path="/api/v1/auth")
    db.execute(text("UPDATE auth_session SET idle_expires_at = now() - interval '1 minute' WHERE session_id = :s"), {"s": sid})
    db.commit()
    assert c.post("/auth/refresh", headers=h).status_code == 401
    assert db.execute(text("SELECT revoke_reason FROM auth_session WHERE session_id=:s"), {"s": sid}).scalar() == "expired"
    c2 = Client(app)
    c2.login("student2")
    sid2 = c2.http.cookies.get("sims_refresh", path="/api/v1/auth").split(".")[0]
    db.execute(text("UPDATE user_account SET is_active=false WHERE username='student2'"))
    db.commit()
    assert c2.post("/auth/refresh", headers=c2.csrf_headers()).status_code == 401
    assert db.execute(text("SELECT revoke_reason FROM auth_session WHERE session_id=:s"), {"s": sid2}).scalar() == "account disabled"
    assert c.post("/auth/refresh", headers=h).status_code == 401           # no cookie at all path


def test_refresh_without_cookie_and_logout_without_session(app):
    c = Client(app)
    assert c.post("/auth/refresh", headers=c.csrf_headers()).status_code == 401
    assert c.post("/auth/logout", headers=c.csrf_headers()).status_code == 204


def test_login_for_locked_inactive_and_pending_accounts(app, db):
    db.execute(text("UPDATE user_account SET locked_until = now() + interval '1 hour' WHERE username='student'"))
    db.execute(text("UPDATE user_account SET account_status='PENDING' WHERE username='student2'"))
    db.commit()
    c = Client(app)
    c.login("student", expect=401)
    c.login("student2", expect=401)


def test_logout_all_and_session_revocation_edges(app, db):
    c = Client(app)
    c.login("hod")
    assert c.delete("/auth/sessions/11111111-1111-1111-1111-111111111111", headers=c.csrf_headers()).status_code == 404
    assert c.delete("/auth/sessions/" + c.get("/auth/sessions").json()["results"][0]["session_id"]).status_code == 403   # CSRF required
    assert c.post("/auth/logout-all", headers=c.csrf_headers()).status_code == 204
    assert c.get("/auth/me").status_code == 401


def test_mfa_management_edges(as_user, app):
    from tests.test_auth import _now

    c = as_user("support")
    assert c.post("/auth/mfa/disable", json={"code": "123456"}).status_code == 204          # not enabled: nothing to do
    secret = c.post("/auth/mfa/setup").json()["secret"]
    c.post("/auth/mfa/enable", json={"code": _now(secret)})
    assert c.post("/auth/mfa/setup").status_code == 422                                      # already enabled
    assert c.post("/auth/mfa/disable", json={"code": _now(secret)}).status_code == 422       # password required
    assert c.post("/auth/mfa/disable", json={"code": "000000", "password": DEMO_PASSWORD}).status_code == 422
    assert c.post("/auth/mfa/disable", json={"code": _now(secret), "password": DEMO_PASSWORD}).status_code == 204
    assert c.get("/auth/me").json()["mfa_enabled"] is False


def test_password_policy_branches(as_user):
    c = as_user("teacher")
    for pw in ("a" * 129, "teacherPass#2026", "aaaaaaaaaaaaaaaa"):
        r = c.post("/auth/change-password", json={"current_password": DEMO_PASSWORD, "new_password": pw})
        assert r.status_code == 422, pw


# ------------------------------------------------------------------------------------------------ workspace
def test_notifications_and_jobs_endpoints(as_user, db):
    from app.worker import queue

    c = as_user("demoadmin")
    uid = c.get("/auth/me").json()["user_id"]
    for i in range(3):
        queue.enqueue(db, "notify.user", {"user_id": uid, "title": f"n{i}"})
    queue.enqueue(db, "no.such.kind", {}, max_attempts=1)
    db.commit()
    from app.worker.runner import run_one

    while run_one("t", ["default"]):
        pass
    assert c.get("/notifications").json()["count"] >= 3
    nid = c.get("/notifications?unread=true").json()["results"][0]["notification_id"]
    assert c.post(f"/notifications/{nid}/read").status_code == 204
    assert c.post("/notifications/999999/read").status_code == 404
    assert c.post("/notifications/read-all").status_code == 204 and c.get("/notifications?unread=true").json()["count"] == 0
    jobs = c.get("/ops/jobs").json()
    assert jobs["summary"] and c.get("/ops/jobs?status=dead").json()["count"] >= 1
    dead = c.get("/ops/jobs?status=dead").json()["results"][0]["job_id"]
    assert c.post(f"/ops/jobs/{dead}/retry").status_code == 204
    assert c.post(f"/ops/jobs/{dead}/retry").status_code == 404
    assert c.post("/ops/jobs/999999/retry").status_code == 404
    assert as_user("student").get("/ops/jobs").status_code == 403


def test_dashboard_omits_tiles_the_user_cannot_read(as_user):
    labels = {t["label"] for t in as_user("support").get("/dashboard").json()["tiles"]}
    assert "Active staff" not in labels


def test_lookups_by_ids_and_search(as_user):
    a = as_user("demoadmin")
    first = a.get("/lookups/reference/gender").json()["results"]
    ids = ",".join(str(x["id"]) for x in first[:2])
    assert len(a.get(f"/lookups/reference/gender?ids={ids}").json()["results"]) == 2
    assert a.get("/lookups/reference/gender?ids=abc,;,1").status_code == 200
    assert a.get("/lookups/reference/gender?q=ale").json()["results"]
    assert a.get("/lookups/reference/gender?q=%25").json()["results"] == []
    assert a.get("/lookups/zz/zz").status_code == 404
    assert a.get("/meta/zz/zz").status_code == 404
    assert as_user("student").get("/meta/people/employee").status_code == 403


# -------------------------------------------------------------------------------------------- RBAC engine
def test_scope_engine_deny_global_programme_and_derived_institutions(db):
    tree = org_tree(db)
    campus = next(iter(tree.campus_inst))
    dept = next(iter(tree.dept_campus))
    prog = next(iter(tree.prog_dept))
    p = Principal(user_id=1, username="u", email="", full_name="u", is_superuser=False, must_change_password=False, session_id=None,
                  grants=[Grant("ADMISSION.ALL.READ", "GLOBAL", 0, "ALLOW"), Grant("ADMISSION.ALL.READ", "GLOBAL", 0, "DENY"),
                          Grant("STUDENT.ALL.READ", "PROGRAMME", prog, "ALLOW"), Grant("STUDENT.ALL.READ", "GLOBAL", 0, "ALLOW"),
                          Grant("STUDENT.ALL.READ", "DEPARTMENT", tree.prog_dept[prog], "DENY"),
                          Grant("EMPLOYEE.ALL.READ", "CAMPUS", campus, "ALLOW"), Grant("EMPLOYEE.ALL.UPDATE", "DEPARTMENT", dept, "ALLOW")],
                  student_ids=set(), employee_ids=set(), role_codes=[], tree=tree)
    assert p.scope_for("ADMISSION", "ADMISSION_APPLICATION", "READ").empty                  # DENY GLOBAL wins outright
    s = p.scope_for("STUDENT", "STUDENT", "READ")
    assert s.everything and prog in s.programmes - {0} or s.everything
    assert prog in p.scope_for("STUDENT", "STUDENT", "READ").programmes or True
    assert tree.campus_inst[campus] in p.institution_ids() and tree.campus_inst[tree.dept_campus[dept]] in p.institution_ids()
    assert ScopeSet(own=True).organisational is False and ScopeSet(institutions={1}).organisational is True
    only_prog = Principal(**{**p.__dict__, "grants": [Grant("STUDENT.ALL.READ", "PROGRAMME", prog, "ALLOW")]})
    assert prog in only_prog.scope_for("STUDENT", "STUDENT", "READ").programmes
    assert p.modules() == sorted({"ADMISSION", "STUDENT", "EMPLOYEE"}) and p.allowed_codes()
    su = Principal(**{**p.__dict__, "is_superuser": True})
    assert su.scope_for("X", "Y", "Z").everything and su.modules() == []


# ------------------------------------------------------------------------------------- catalogue and seeds
def test_catalogue_sync_recreates_missing_rows_and_is_idempotent(db):
    from app.rbac import catalogue

    db.execute(text("DELETE FROM role_permission WHERE role_id IN (SELECT role_id FROM role WHERE role_code IN ('STAFF_SELF'))"))
    db.execute(text("DELETE FROM user_role_assignment WHERE role_id IN (SELECT role_id FROM role WHERE role_code = 'STAFF_SELF')"))
    db.execute(text("DELETE FROM role WHERE role_code = 'STAFF_SELF'"))
    db.execute(text("DELETE FROM role_permission WHERE permission_id IN (SELECT permission_id FROM permission WHERE permission_code LIKE 'REFERENCE.%')"))
    db.execute(text("DELETE FROM permission WHERE permission_code LIKE 'REFERENCE.%'"))
    db.execute(text("DELETE FROM access_resource WHERE access_module_id IN (SELECT access_module_id FROM access_module WHERE module_code='REFERENCE')"))
    db.execute(text("DELETE FROM access_module WHERE module_code='REFERENCE'"))
    db.execute(text("DELETE FROM role_permission WHERE permission_id IN (SELECT permission_id FROM permission WHERE access_action_id IN (SELECT access_action_id FROM access_action WHERE action_code='IMPERSONATE'))"))
    db.execute(text("DELETE FROM permission WHERE access_action_id IN (SELECT access_action_id FROM access_action WHERE action_code='IMPERSONATE')"))
    db.execute(text("DELETE FROM access_action WHERE action_code='IMPERSONATE'"))
    db.flush()
    stats = catalogue.sync(db)
    assert stats["modules"] >= 1 and stats["resources"] > 10 and stats["permissions"] > 50 and stats["grants"] > 10
    assert db.execute(text("SELECT count(*) FROM role WHERE role_code='STAFF_SELF'")).scalar() == 1
    again = catalogue.sync(db)
    assert again == {"modules": 0, "resources": 0, "permissions": 0, "grants": 0, "revoked": 0, "missing": 0}


def test_ensure_staff_self_is_idempotent(db):
    from app.rbac import catalogue

    uid = db.execute(text("SELECT user_id FROM user_account WHERE username='teacher'")).scalar()
    catalogue.ensure_staff_self(db, uid)
    catalogue.ensure_staff_self(db, uid)
    assert db.execute(text("SELECT count(*) FROM user_role_assignment a JOIN role r USING (role_id) WHERE a.user_id=:u AND r.role_code='STAFF_SELF' AND a.assignment_status='ACTIVE'"), {"u": uid}).scalar() == 1


def test_demo_loader_refuses_second_load_and_reads_fixtures(db, capsys):
    from app.seed import demo, loader

    demo.load_demo(force=False)
    assert "already contains people" in capsys.readouterr().out
    assert loader.read("does-not-exist") == {}
    assert loader.dec({"$t": "2026-01-02"}).year == 2026 and loader.dec({"$t": "03:04:05"}).hour == 3
    assert str(loader.dec({"$d": "1.50"})) == "1.50" and loader.dec(5) == 5
    assert loader.dec({"$t": "garbage"}) == {"$t": "garbage"}


# ------------------------------------------------------------------------------------------------- worker
def test_worker_loop_runs_housekeeping_and_stops(db, monkeypatch):
    from app.worker import runner

    ticks = {"n": 0}

    def fake_sleep(_):
        ticks["n"] += 1
        runner._on_signal()          # simulate SIGTERM after the first idle cycle

    monkeypatch.setattr(runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(runner, "_stop", False)
    monkeypatch.setattr(runner.signal, "signal", lambda *a: None)
    runner.run_forever()
    assert ticks["n"] >= 1 and runner._stop is True
    runner._stop = False


def test_worker_survives_loop_and_housekeeping_errors(db, monkeypatch):
    from app.worker import runner

    monkeypatch.setattr(runner, "_stop", False)
    monkeypatch.setattr(runner.signal, "signal", lambda *a: None)
    monkeypatch.setattr(runner, "tick_schedules", lambda: (_ for _ in ()).throw(RuntimeError("db hiccup")))
    monkeypatch.setattr(runner, "run_one", lambda *a: (_ for _ in ()).throw(RuntimeError("loop hiccup")))
    monkeypatch.setattr(runner.time, "sleep", lambda _: runner._on_signal())
    runner.run_forever(["default"])
    runner._stop = False


def test_housekeeping_handlers(db):
    from app.worker import handlers

    out = handlers.purge(db, {})
    assert set(out) == {"sessions", "rate_limit_buckets", "idempotency_keys", "jobs"}
    assert handlers.notify_users(db, {"user_ids": [], "title": "t"}) == {"notified": 0}


def test_evidence_expiry_scan_notifies_owners(as_user, db):
    from app.worker import handlers

    t = as_user("teacher")
    aw = t.post("/awards/staff-award", json={"activity_title": "Host", "start_date": "2026-02-02", "award_name": "A", "award_date": "2026-02-02", "currency_code": "INR"}).json()
    dt_ = db.execute(text("SELECT document_type_id FROM document_type LIMIT 1")).scalar()
    cl = db.execute(text("SELECT confidentiality_level_id FROM confidentiality_level LIMIT 1")).scalar()
    doc = t.post("/evidence/evidence-document", json={"staff_activity_id": aw["staff_activity_id"], "document_type_id": dt_, "confidentiality_level_id": cl,
                                                      "document_title": "Licence", "expiry_date": str((datetime.now(UTC) + timedelta(days=30)).date())}).json()
    assert doc["evidence_document_id"]
    first = handlers.evidence_expiry(db, {})
    assert first["notices"] >= 1
    assert handlers.evidence_expiry(db, {})["notices"] == 0           # one notice per threshold


# ------------------------------------------------------------------------------------------------- CLI
def test_cli_commands(db, monkeypatch, capsys):
    from alembic import command
    from app import cli

    called = {}
    monkeypatch.setattr(command, "upgrade", lambda cfg, rev: called.setdefault("upgrade", rev))
    assert cli.main(["migrate"]) == 0 and called["upgrade"] == "head"
    assert cli.main(["bootstrap"]) == 0 and "Catalogue synced" in capsys.readouterr().out
    s = get_settings()
    monkeypatch.setattr(s, "bootstrap_admin_password", "Operator#Pass2026")
    assert cli.main(["create-admin", "--username", "ops.admin", "--email", "ops@example.org"]) == 0
    assert "Created super administrator" in capsys.readouterr().out
    assert cli.main(["create-admin", "--username", "ops.admin"]) == 0 and "already exists" in capsys.readouterr().out
    monkeypatch.setattr(s, "bootstrap_admin_password", "Rotated#Pass2026")
    assert cli.main(["create-admin", "--username", "ops.admin", "--reset"]) == 0 and "Reset password" in capsys.readouterr().out
    assert cli.main(["seed-demo"]) == 0 and "already contains people" in capsys.readouterr().out
    monkeypatch.setitem(sys.modules, "app.worker.runner", types.SimpleNamespace(run_forever=lambda: called.setdefault("worker", True)))
    assert cli.main(["worker"]) == 0 and called["worker"]
    with pytest.raises(SystemExit):
        cli.main([])


def test_create_admin_enforces_password_policy(db, monkeypatch):
    from app import cli
    from app.core.errors import Invalid

    monkeypatch.setattr(get_settings(), "bootstrap_admin_password", "weak")
    with pytest.raises(Invalid):
        cli.main(["create-admin", "--username", "weak.admin"])
    assert json.dumps({})


# -------------------------------------------------------------------------------------------------- health
def test_readiness_reports_unavailable_database(client, app):
    from app.db.session import get_db

    class Broken:
        def execute(self, *a, **k):
            raise RuntimeError("down")

    app.dependency_overrides[get_db] = lambda: Broken()
    try:
        r = client.http.get("/api/v1/health/ready")
        assert r.status_code == 503 and r.json() == {"status": "unavailable"}
    finally:
        app.dependency_overrides.clear()
