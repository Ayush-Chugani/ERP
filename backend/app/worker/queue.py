"""PostgreSQL-backed job queue (FOR UPDATE SKIP LOCKED) with retries, back-off, dedupe and scheduling."""
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.platform import Job

HANDLERS: dict[str, Callable[[Session, dict], Any]] = {}
STALE_AFTER = timedelta(minutes=15)


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn

    return deco


def enqueue(db: Session, kind: str, payload: dict | None = None, *, queue: str = "default", priority: int = 100,
            run_at: datetime | None = None, dedupe_key: str | None = None, max_attempts: int = 5,
            user_id: int | None = None) -> int | None:
    """Add a job inside the caller's transaction (so it exists only if the business change commits).
    Returns None when an identical queued/running job (same dedupe_key) already exists."""
    row = db.execute(text(
        "INSERT INTO job (queue, kind, payload, priority, run_at, dedupe_key, max_attempts, created_by_id) "
        "VALUES (:q, :k, CAST(:p AS jsonb), :pr, COALESCE(:r, now()), :d, :m, :u) "
        "ON CONFLICT (dedupe_key) WHERE status IN ('queued','running') DO NOTHING RETURNING job_id"),
        {"q": queue, "k": kind, "p": json.dumps(payload or {}), "pr": priority, "r": run_at,
         "d": dedupe_key, "m": max_attempts, "u": user_id}).first()
    return row[0] if row else None


def claim(db: Session, worker_id: str, queues: list[str]) -> Job | None:
    row = db.execute(text(
        "UPDATE job SET status='running', locked_by=:w, locked_at=now(), attempts=attempts+1 "
        "WHERE job_id = (SELECT job_id FROM job WHERE status='queued' AND run_at <= now() AND queue = ANY(:qs) "
        "ORDER BY priority, run_at, job_id FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING job_id"),
        {"w": worker_id, "qs": queues}).first()
    return db.get(Job, row[0]) if row else None


def succeed(db: Session, job: Job, result: Any = None) -> None:
    job.status, job.finished_at, job.result, job.locked_by = "succeeded", datetime.now(UTC), result, None


def fail(db: Session, job: Job, error: str) -> None:
    job.last_error = error[:4000]
    job.locked_by = None
    if job.attempts >= job.max_attempts:
        job.status, job.finished_at = "dead", datetime.now(UTC)
    else:
        job.status = "queued"
        job.run_at = datetime.now(UTC) + timedelta(seconds=min(3600, 30 * 2 ** (job.attempts - 1)))


def reap_stale(db: Session) -> int:
    """Return jobs abandoned by a crashed worker to the queue."""
    return db.execute(text("UPDATE job SET status='queued', locked_by=NULL WHERE status='running' AND locked_at < :t"),
                      {"t": datetime.now(UTC) - STALE_AFTER}).rowcount
