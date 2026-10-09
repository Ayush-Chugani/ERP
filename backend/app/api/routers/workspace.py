"""Signed-in user workspace: dashboard counters, notifications and background-job monitoring."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.api.deps import active_principal, require
from app.config import get_settings
from app.core.errors import Forbidden, NotFound
from app.db.session import get_db
from app.models.platform import Job, Notification
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry
from app.resources.spec import REGISTRY

router = APIRouter(tags=["workspace"])

# (label, table, filters, link)  filters are column -> list of accepted values
TILES = [
    ("Active students", "student", {"student_status": ["ACTIVE"]}, "people/student"),
    ("Applicants", "student", {"student_status": ["APPLICANT"]}, "people/student"),
    ("Active staff", "employee", {"employment_status": ["ACTIVE"]}, "people/employee"),
    ("Programmes", "programme", {}, "organization/programme"),
    ("Admission applications", "admission_application", {}, "admissions/admission-application"),
    ("Course offerings", "course_offering", {"status": ["OPEN", "ACTIVE"]}, "curriculum/course-offering"),
    ("Open grievances", "grievance", {"status": ["SUBMITTED", "ASSIGNED", "UNDER_REVIEW"]}, "support/grievance"),
    ("Certificate requests to review", "certificate_request", {"request_status": ["SUBMITTED", "UNDER_REVIEW"]},
     "documents/certificate-request"),
    ("Attendance corrections pending", "attendance_correction_request", {"request_status": ["PENDING"]},
     "attendance/attendance-correction-request"),
    ("Announcements awaiting approval", "announcement", {"approval_status": ["PENDING"]},
     "communication/announcement"),
    ("Active mentor assignments", "mentor_assignment", {"assignment_status": ["ACTIVE"]},
     "support/mentor-assignment"),
    ("Open feedback cycles", "feedback_cycle", {"status": ["OPEN"]}, "feedback/feedback-cycle"),
    ("Staff activities", "staff_activity", {}, "staff-activities/staff-activity"),
]

# Tiles that stay meaningful when a user can only see their own records (students, self-service staff).
PERSONAL = {"Open grievances", "Certificate requests to review", "Active mentor assignments"}


@router.get("/dashboard")
def dashboard(principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    build_registry()
    tiles = []
    for label, table, filters, link in TILES:
        spec = REGISTRY.get(table)
        if spec is None:
            continue
        if not principal.is_superuser and not principal.can(spec.perm_module, spec.perm_resource, "READ"):
            continue
        q, _ = crud.scoped(spec, principal, "READ")
        if label not in PERSONAL and not principal.is_superuser and not crud.scope_for(spec, principal, "READ").organisational:
            continue        # an organisation-wide counter would read "1" for someone who only sees themselves
        t = spec.model.__table__
        for col, vals in filters.items():
            if col in t.c:
                q = q.where(t.c[col].in_(vals))
        count = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
        tiles.append({"label": label, "value": count, "link": link})
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == principal.user_id, Notification.read_at.is_(None)))
    return {"tiles": tiles, "unread_notifications": unread}


@router.get("/notifications")
def notifications(unread: bool = False, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                  principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == principal.user_id)
    if unread:
        q = q.where(Notification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Notification.notification_id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
    return {"count": total, "page": page, "page_size": page_size, "results": [
        {"notification_id": n.notification_id, "title": n.title, "body": n.body, "link": n.link,
         "created_at": n.created_at, "read_at": n.read_at} for n in rows]}


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    n = db.scalar(select(Notification).where(Notification.notification_id == notification_id,
                                              Notification.user_id == principal.user_id))
    if n is None:
        raise NotFound()
    n.read_at = n.read_at or datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == principal.user_id, Notification.read_at.is_(None))
               .values(read_at=datetime.now(UTC)))
    db.commit()
    return Response(status_code=204)


@router.get("/ops/jobs")
def jobs(status: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
         principal: Principal = Depends(require("IAM", "OPERATIONS", "CONFIGURE")), db: Session = Depends(get_db)):
    q = select(Job)
    if status:
        q = q.where(Job.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Job.job_id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
    summary = {s: n for s, n in db.execute(text("SELECT status, count(*) FROM job GROUP BY status"))}
    return {"count": total, "summary": summary, "results": [
        {"job_id": j.job_id, "kind": j.kind, "queue": j.queue, "status": j.status, "attempts": j.attempts,
         "max_attempts": j.max_attempts, "run_at": j.run_at, "created_at": j.created_at,
         "finished_at": j.finished_at, "last_error": j.last_error} for j in rows]}


@router.post("/ops/jobs/{job_id}/retry", status_code=204)
def retry_job(job_id: int, principal: Principal = Depends(require("IAM", "OPERATIONS", "CONFIGURE")),
              db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.status not in ("dead", "failed"):
        raise NotFound("No failed job with that id.")
    job.status, job.attempts, job.run_at, job.last_error = "queued", 0, datetime.now(UTC), None
    db.commit()
    return Response(status_code=204)


@router.get("/ops/overview")
def owner_overview(principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Application-owner dashboard: people, access, activity, background work and system health in one call.
    Super administrators only (it spans every institution and exposes operational detail)."""
    if not principal.is_superuser:
        raise Forbidden()
    one = lambda sql, **p: db.execute(text(sql), p).scalar() or 0  # noqa: E731
    cfg = get_settings()
    users = {
        "total": one("SELECT count(*) FROM user_account"),
        "active": one("SELECT count(*) FROM user_account WHERE is_active"),
        "locked": one("SELECT count(*) FROM user_account WHERE locked_until > now()"),
        "with_mfa": one("SELECT count(*) FROM user_account WHERE multi_factor_enabled"),
        "super_admins": one("SELECT count(*) FROM user_account WHERE is_superuser AND is_active"),
        "must_change_password": one("SELECT count(*) FROM user_account WHERE must_change_password"),
    }
    by_role = [{"role": r, "name": n, "users": c} for r, n, c in db.execute(text(
        "SELECT r.role_code, r.role_name, count(DISTINCT a.user_id) FROM role r JOIN user_role_assignment a ON a.role_id = r.role_id "
        "AND a.assignment_status = 'ACTIVE' GROUP BY 1, 2 ORDER BY 3 DESC, 1"))]
    logins = db.execute(text(
        "SELECT count(*) FILTER (WHERE was_successful), count(*) FILTER (WHERE NOT was_successful) FROM login_audit "
        "WHERE login_at > now() - interval '24 hours'")).one()
    recent_logins = [{"username": u, "ok": ok, "at": at, "ip": ip, "reason": why} for u, ok, at, ip, why in db.execute(text(
        "SELECT username_attempted, was_successful, login_at, ip_address, failure_reason FROM login_audit ORDER BY login_audit_id DESC LIMIT 8"))]
    recent_audit = [{"at": at, "actor": a, "action": act, "module": m, "resource": r, "record_id": rid} for at, a, act, m, r, rid in db.execute(text(
        "SELECT l.occurred_at, u.username, l.action, l.module, l.resource, l.record_id FROM audit_log l "
        "LEFT JOIN user_account u ON u.user_id = l.actor_user_id ORDER BY l.audit_id DESC LIMIT 8"))]
    jobs_summary = {s: n for s, n in db.execute(text("SELECT status, count(*) FROM job GROUP BY status"))}
    last_job = db.execute(text("SELECT max(finished_at) FROM job WHERE status = 'done'")).scalar()
    return {
        "generated_at": datetime.now(UTC),
        "people": {
            "students": one("SELECT count(*) FROM student WHERE student_status = 'ACTIVE'"),
            "staff": one("SELECT count(*) FROM employee WHERE employment_status = 'ACTIVE'"),
            "institutions": one("SELECT count(*) FROM institution"), "campuses": one("SELECT count(*) FROM campus"),
            "departments": one("SELECT count(*) FROM department"), "programmes": one("SELECT count(*) FROM programme"),
        },
        "users": users, "users_by_role": by_role,
        "sessions": {"active": one("SELECT count(*) FROM auth_session WHERE revoked_at IS NULL AND expires_at > now() AND idle_expires_at > now()")},
        "logins_24h": {"successful": logins[0], "failed": logins[1]},
        "recent_logins": recent_logins, "recent_audit": recent_audit,
        "jobs": {"summary": jobs_summary, "last_completed_at": last_job},
        "workflow": {
            "grievances_open": one("SELECT count(*) FROM grievance WHERE status IN ('SUBMITTED','ASSIGNED','UNDER_REVIEW')"),
            "applications_in_progress": one("SELECT count(*) FROM admission_application WHERE application_status NOT IN ('ADMITTED','REJECTED','WITHDRAWN','CANCELLED')"),
            "announcements_pending": one("SELECT count(*) FROM announcement WHERE approval_status = 'PENDING'"),
        },
        "system": {
            "environment": cfg.env, "schema": one("SELECT version_num FROM alembic_version") or None,
            "storage": cfg.storage_backend, "ai_enabled": bool(cfg.ai_enabled and cfg.ai_api_key), "ai_model": cfg.ai_model,
            "database": "connected",
        },
    }
