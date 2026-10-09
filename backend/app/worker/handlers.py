"""Background job handlers."""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.platform import Notification
from app.worker.queue import handler

log = logging.getLogger("sims.jobs")


@handler("maintenance.purge")
def purge(db: Session, payload: dict) -> dict:
    now = datetime.now(UTC)
    sessions = db.execute(text(
        "DELETE FROM auth_session WHERE (revoked_at IS NOT NULL AND revoked_at < :t) OR expires_at < :t"),
        {"t": now - timedelta(days=30)}).rowcount
    buckets = db.execute(text("DELETE FROM rate_limit_bucket WHERE window_start < :t"),
                         {"t": int(now.timestamp()) - 86400}).rowcount
    idem = db.execute(text("DELETE FROM idempotency_key WHERE created_at < :t"),
                      {"t": now - timedelta(days=2)}).rowcount
    jobs = db.execute(text("DELETE FROM job WHERE status = 'succeeded' AND finished_at < :t"),
                      {"t": now - timedelta(days=14)}).rowcount
    return {"sessions": sessions, "rate_limit_buckets": buckets, "idempotency_keys": idem, "jobs": jobs}


@handler("notify.user")
def notify_user(db: Session, payload: dict) -> dict:
    db.add(Notification(user_id=payload["user_id"], title=payload["title"][:200],
                        body=(payload.get("body") or "")[:2000], link=payload.get("link")))
    return {"notified": 1}


@handler("notify.users")
def notify_users(db: Session, payload: dict) -> dict:
    ids = payload["user_ids"]
    for uid in ids:
        db.add(Notification(user_id=uid, title=payload["title"][:200], body=(payload.get("body") or "")[:2000],
                            link=payload.get("link")))
    return {"notified": len(ids)}


@handler("memberships.expire")
def memberships_expire(db: Session, payload: dict) -> dict:
    n = db.execute(text(
        "UPDATE staff_professional_membership SET membership_status = 'EXPIRED' WHERE membership_status = 'ACTIVE' "
        "AND NOT is_lifetime_membership AND membership_expiry_date IS NOT NULL AND membership_expiry_date < CURRENT_DATE")).rowcount
    return {"expired": n}


@handler("documents.expire")
def documents_expire(db: Session, payload: dict) -> dict:
    n = db.execute(text(
        "UPDATE student_document SET verification_status = 'EXPIRED' WHERE verification_status IN ('PENDING','VERIFIED') "
        "AND expiry_date IS NOT NULL AND expiry_date < CURRENT_DATE")).rowcount
    return {"expired": n}


EVIDENCE_THRESHOLDS = (90, 60, 30, 7, 0)


@handler("evidence.expiry_scan")
def evidence_expiry(db: Session, payload: dict) -> dict:
    """Warn document owners as evidence approaches expiry (once per threshold)."""
    created = 0
    for days in EVIDENCE_THRESHOLDS:
        rows = db.execute(text(
            "SELECT d.evidence_document_id, d.document_title, d.expiry_date, a.employee_id FROM evidence_document d "
            "JOIN staff_activity a ON a.staff_activity_id = d.staff_activity_id "
            "WHERE d.deleted_at IS NULL AND d.is_active AND d.expiry_date = CURRENT_DATE + :d "
            "AND NOT EXISTS (SELECT 1 FROM evidence_expiry_notice n WHERE n.document_id = d.evidence_document_id AND n.threshold_days = :d)"),
            {"d": days}).all()
        for doc_id, title, expiry, employee_id in rows:
            db.execute(text("INSERT INTO evidence_expiry_notice (document_id, expiry_date, threshold_days, delivered_at, attempts) "
                            "VALUES (:i, :e, :t, now(), 1)"), {"i": doc_id, "e": expiry, "t": days})
            users = [u for (u,) in db.execute(text("SELECT user_id FROM person_account_link WHERE employee_id = :e"), {"e": employee_id})]
            if users:
                when = "today" if days == 0 else f"in {days} days"
                db.add(Notification(user_id=users[0], title=f"Evidence expires {when}", body=title,
                                    link=f"/r/evidence/evidence-document/{doc_id}"))
            created += 1
    return {"notices": created}


@handler("announcement.deliver")
def announcement_deliver(db: Session, payload: dict) -> dict:
    from app.resources.domain_hooks import deliver_announcement

    return {"recipients": deliver_announcement(db, payload["announcement_id"])}
