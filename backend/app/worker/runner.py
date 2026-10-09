"""Worker process: schedules recurring jobs, claims queued jobs and runs their handlers."""
import json
import logging
import os
import signal
import socket
import time

from sqlalchemy import text

from app.config import get_settings
from app.db.session import db_session
from app.models.platform import Job
from app.worker import handlers  # noqa: F401  (registers handlers)
from app.worker.queue import HANDLERS, claim, fail, reap_stale, succeed

log = logging.getLogger("sims.worker")
_stop = False


def _on_signal(*_):
    global _stop
    _stop = True


def tick_schedules() -> int:
    """Enqueue every due recurring job exactly once, even with several workers running."""
    with db_session() as db:
        rows = db.execute(text(
            "UPDATE job_schedule SET next_run_at = now() + make_interval(secs => interval_seconds) "
            "WHERE enabled AND next_run_at <= now() RETURNING kind, payload, schedule_id")).all()
        for kind, payload, sid in rows:
            db.execute(text(
                "INSERT INTO job (queue, kind, payload, dedupe_key, priority) "
                "VALUES ('default', :k, CAST(:p AS jsonb), :d, 200) "
                "ON CONFLICT (dedupe_key) WHERE status IN ('queued','running') DO NOTHING"),
                {"k": kind, "p": json.dumps(payload), "d": f"schedule:{sid}"})
        return len(rows)


def run_one(worker_id: str, queues: list[str]) -> bool:
    """Claim and execute one job. Returns False when the queue is empty."""
    with db_session() as db:
        job = claim(db, worker_id, queues)
        if job is None:
            return False
        job_id, kind, payload = job.job_id, job.kind, dict(job.payload or {})
    fn = HANDLERS.get(kind)
    with db_session() as db:
        try:
            if fn is None:
                raise RuntimeError(f"no handler registered for '{kind}'")
            result = fn(db, payload)
            db.flush()
            succeed(db, db.get(Job, job_id), result if isinstance(result, (dict, list)) else None)
            log.info("job %s %s ok", job_id, kind)
            return True
        except Exception as exc:  # noqa: BLE001 - a failing job must never kill the worker
            db.rollback()
            failed = db.get(Job, job_id)
            fail(db, failed, f"{type(exc).__name__}: {exc}")
            log.exception("job %s %s failed (attempt %s)", job_id, kind, failed.attempts)
            return True


def run_forever(queues: list[str] | None = None) -> None:
    s = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    queues = queues or ["default"]
    log.info("worker %s started (queues=%s)", worker_id, queues)
    last_housekeeping = 0.0
    while not _stop:
        now = time.monotonic()
        if now - last_housekeeping > 30:
            last_housekeeping = now
            try:
                tick_schedules()
                with db_session() as db:
                    reap_stale(db)
            except Exception:  # noqa: BLE001
                log.exception("housekeeping failed")
        try:
            worked = run_one(worker_id, queues)
        except Exception:  # noqa: BLE001
            log.exception("worker loop error")
            worked = False
        if not worked:
            time.sleep(s.worker_poll_seconds)
    log.info("worker stopped")
