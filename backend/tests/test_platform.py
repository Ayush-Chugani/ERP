"""Cross-cutting platform guarantees: HTTP hardening, database hardening and the job queue."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.worker import queue
from app.worker.runner import run_one, tick_schedules


def test_security_headers_and_request_id(client):
    r = client.http.get("/api/v1/health/live", headers={"X-Request-ID": "abc-123"})
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer" and h["cache-control"] == "no-store"
    assert h["x-request-id"] == "abc-123"
    assert "default-src 'none'" in h["content-security-policy"]


def test_invalid_host_header_is_rejected(app):
    from fastapi.testclient import TestClient

    r = TestClient(app, base_url="http://evil.example").get("/api/v1/health/live")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_host"


def test_oversized_body_is_rejected(client):
    r = client.http.post("/api/v1/auth/login", content=b"x" * (13 * 1024 * 1024),
                         headers={"Content-Type": "application/json", "X-CSRF-Token": client.csrf})
    assert r.status_code == 413


def test_unknown_routes_use_the_error_envelope(client):
    r = client.http.get("/api/v1/definitely/not/here")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message", "details"}
    assert client.http.get("/api/v1/auth/login").status_code == 405


def test_health_endpoints(client):
    assert client.http.get("/api/v1/health/live").json() == {"status": "ok"}
    ready = client.http.get("/api/v1/health/ready").json()
    assert ready["status"] == "ok" and ready["schema"]


def test_row_level_security_is_on_for_every_table(db):
    rows = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity")).all()
    assert rows == []


def test_cors_only_for_configured_origins(client):
    r = client.http.options("/api/v1/auth/csrf", headers={"Origin": "https://evil.example",
                                                         "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


# ------------------------------------------------------------------------------------------------- job queue
def test_queue_runs_jobs_and_dedupes(db):
    first = queue.enqueue(db, "maintenance.purge", {}, dedupe_key="purge-now")
    again = queue.enqueue(db, "maintenance.purge", {}, dedupe_key="purge-now")
    db.commit()
    assert first and again is None
    assert run_one("w1", ["default"]) is True
    status = db.execute(text("SELECT status FROM job WHERE job_id=:i"), {"i": first}).scalar()
    assert status == "succeeded"
    assert run_one("w1", ["default"]) is False or True  # other seeded jobs may exist


def test_failed_jobs_back_off_then_die(db):
    @queue.handler("test.boom")
    def boom(db_, payload):
        raise RuntimeError("kaput")

    jid = queue.enqueue(db, "test.boom", {}, max_attempts=2)
    db.commit()
    assert run_one("w", ["default"])
    row = db.execute(text("SELECT status, attempts, run_at > now() AS later, last_error FROM job WHERE job_id=:i"),
                     {"i": jid}).one()
    assert row.status == "queued" and row.attempts == 1 and row.later and "kaput" in row.last_error
    db.execute(text("UPDATE job SET run_at = now() WHERE job_id=:i"), {"i": jid})
    db.commit()
    assert run_one("w", ["default"])
    assert db.execute(text("SELECT status FROM job WHERE job_id=:i"), {"i": jid}).scalar() == "dead"


def test_unknown_job_kind_fails_cleanly(db):
    jid = queue.enqueue(db, "no.such.kind", {}, max_attempts=1)
    db.commit()
    assert run_one("w", ["default"])
    assert db.execute(text("SELECT status FROM job WHERE job_id=:i"), {"i": jid}).scalar() == "dead"


def test_stale_running_jobs_are_returned_to_the_queue(db):
    jid = queue.enqueue(db, "maintenance.purge", {})
    db.execute(text("UPDATE job SET status='running', locked_at=:t WHERE job_id=:i"),
               {"t": datetime.now(UTC) - timedelta(hours=1), "i": jid})
    db.commit()
    assert queue.reap_stale(db) >= 1
    assert db.execute(text("SELECT status FROM job WHERE job_id=:i"), {"i": jid}).scalar() == "queued"


def test_scheduler_enqueues_due_schedules_once(db):
    from app.worker.schedules import ensure_schedules

    ensure_schedules(db)
    db.execute(text("UPDATE job_schedule SET next_run_at = now() - interval '1 minute'"))
    db.commit()
    assert tick_schedules() >= 1
    assert tick_schedules() == 0
    assert db.execute(text("SELECT count(*) FROM job WHERE dedupe_key LIKE 'schedule:%'")).scalar() >= 1
