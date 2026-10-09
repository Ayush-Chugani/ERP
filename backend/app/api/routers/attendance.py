"""Attendance: session rosters, bulk marking governed by the section's attendance policy, and shortage summaries."""
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import active_principal, client_ip
from app.core.errors import Conflict, Invalid, NotFound
from app.db.session import get_db
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry
from app.services import audit

router = APIRouter(prefix="/attendance", tags=["Attendance"])
Status = Literal["PRESENT", "ABSENT", "LATE", "EXCUSED", "ON_DUTY"]


class Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: int
    status: Status
    remarks: str = Field(default="", max_length=500)


class MarksIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    marks: list[Mark] = Field(min_length=1, max_length=500)


def _session(db: Session, principal: Principal, session_id: int, action: str, lock: bool = False):
    return crud.get_one(db, build_registry()["class_session"], principal, session_id, action, lock=lock)


def policy_weights(db: Session, policy_id: int | None, status: str) -> tuple[Decimal, Decimal]:
    """(credit, denominator) a status contributes to the attendance percentage under the session's policy."""
    rules = db.execute(text("SELECT rules FROM attendance_policy WHERE id = :p"), {"p": policy_id}).scalar() if policy_id else None
    entry = (rules or {}).get(status)
    if entry is None:
        entry = {"PRESENT": {"credit": "1", "denominator": "1"}, "LATE": {"credit": "1", "denominator": "1"},
                 "ON_DUTY": {"credit": "1", "denominator": "1"}, "ABSENT": {"credit": "0", "denominator": "1"},
                 "EXCUSED": {"credit": "0", "denominator": "0"}}[status]
    return Decimal(str(entry["credit"])), Decimal(str(entry["denominator"]))


@router.get("/sessions/{session_id}/roster")
def roster(session_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    sess = _session(db, principal, session_id, "READ")
    rows = db.execute(text(
        "SELECT st.student_id, st.display_name, st.student_number, s.status_code, a.remarks "
        "FROM course_offering_section_student r "
        "JOIN student_course_registration cr ON cr.course_registration_id = r.course_registration_id "
        "JOIN student_term_registration tr ON tr.term_registration_id = cr.term_registration_id "
        "JOIN student_programme_enrolment e ON e.enrolment_id = tr.enrolment_id "
        "JOIN student st ON st.student_id = e.student_id "
        "LEFT JOIN student_attendance a ON a.class_session_id = :cs AND a.student_id = st.student_id "
        "LEFT JOIN attendance_status s ON s.attendance_status_id = a.attendance_status_id "
        "WHERE r.course_offering_section_id = :sec AND r.roster_status = 'ACTIVE' ORDER BY st.display_name"),
        {"cs": session_id, "sec": sess.course_offering_section_id}).mappings().all()
    return {"class_session_id": session_id, "register_status": sess.register_status, "session_date": sess.session_date,
            "students": [{"student_id": r["student_id"], "name": r["display_name"], "student_number": r["student_number"],
                          "status": r["status_code"], "remarks": r["remarks"]} for r in rows]}


@router.put("/sessions/{session_id}/marks")
def mark(session_id: int, body: MarksIn, request: Request, principal: Principal = Depends(active_principal),
         db: Session = Depends(get_db)):
    sess = _session(db, principal, session_id, "UPDATE", lock=True)
    if sess.register_status not in ("OPEN", "REOPENED"):
        raise Conflict("The register is not open for marking. Open or reopen it first.", code="register_closed")
    seen: set[int] = set()
    statuses = {code: pk for code, pk in db.execute(text("SELECT status_code, attendance_status_id FROM attendance_status"))}
    roster_rows = {r[0]: (r[1], r[2]) for r in db.execute(text(
        "SELECT st.student_id, r.course_offering_section_student_id, r.roster_status "
        "FROM course_offering_section_student r "
        "JOIN student_course_registration cr ON cr.course_registration_id = r.course_registration_id "
        "JOIN student_term_registration tr ON tr.term_registration_id = cr.term_registration_id "
        "JOIN student_programme_enrolment e ON e.enrolment_id = tr.enrolment_id "
        "JOIN student st ON st.student_id = e.student_id "
        "WHERE r.course_offering_section_id = :sec"), {"sec": sess.course_offering_section_id})}
    for m in body.marks:
        if m.student_id in seen:
            raise Invalid(f"Student {m.student_id} appears more than once.")
        seen.add(m.student_id)
        if m.student_id not in roster_rows or roster_rows[m.student_id][1] != "ACTIVE":
            raise Invalid(f"Student {m.student_id} is not on this section's active roster.",
                          details={"student_id": [str(m.student_id)]})
    saved = 0
    for m in body.marks:
        credit, denom = policy_weights(db, sess.policy_id, m.status)
        existing = db.execute(text("SELECT attendance_id, version FROM student_attendance "
                                   "WHERE class_session_id = :c AND student_id = :s FOR UPDATE"),
                              {"c": session_id, "s": m.student_id}).first()
        args = {"c": session_id, "sec": sess.course_offering_section_id, "rs": roster_rows[m.student_id][0],
                "s": m.student_id, "st": statuses[m.status], "cr": credit, "dn": denom, "rm": m.remarks,
                "u": principal.user_id}
        if existing:
            db.execute(text("UPDATE student_attendance SET attendance_status_id=:st, credit=:cr, denominator=:dn, "
                            "remarks=:rm, marked_by_user_id=:u, marked_at=now(), version=version+1 "
                            "WHERE attendance_id=:id"), {**args, "id": existing[0]})
        else:
            db.execute(text(
                "INSERT INTO student_attendance (class_session_id, course_offering_section_id, "
                "course_offering_section_student_id, student_id, attendance_status_id, credit, denominator, remarks, "
                "marked_by_user_id, marked_at, version, exclusion_reason, is_eligible) "
                "VALUES (:c, :sec, :rs, :s, :st, :cr, :dn, :rm, :u, now(), 1, '', true)"), args)
        saved += 1
    audit.record(db, principal, action="mark_attendance", module="ATTENDANCE", resource="class_session",
                 record_id=session_id, after={"students": saved}, request_id=request.state.request_id,
                 ip=client_ip(request))
    db.commit()
    return {"class_session_id": session_id, "saved": saved}


@router.get("/summary")
def summary(course_offering_section_id: int = Query(), student_id: int | None = None,
            principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Attendance percentage per student for a section, with shortage flags against the policy threshold."""
    spec = build_registry()["student_attendance"]
    q, _ = crud.scoped(spec, principal, "READ")
    t = spec.model.__table__
    q = q.where(t.c.course_offering_section_id == course_offering_section_id)
    if student_id is not None:
        q = q.where(t.c.student_id == student_id)
    sub = q.subquery()
    agg = select(sub.c.student_id, func.sum(sub.c.credit), func.sum(sub.c.denominator), func.count()).where(
        sub.c.is_eligible).group_by(sub.c.student_id)
    threshold = db.execute(text(
        "SELECT threshold FROM attendance_policy WHERE section_id = :s ORDER BY number DESC LIMIT 1"),
        {"s": course_offering_section_id}).scalar() or Decimal("75")
    names = {}
    result = []
    for sid, credit, denom, sessions in db.execute(agg):
        pct = (Decimal(credit or 0) / Decimal(denom) * 100).quantize(Decimal("0.01")) if denom else None
        result.append({"student_id": sid, "sessions": sessions, "credit": credit, "denominator": denom,
                       "percentage": pct, "shortage": pct is not None and pct < threshold})
    for r in db.execute(text("SELECT student_id, display_name FROM student WHERE student_id = ANY(:i)"),
                        {"i": [r["student_id"] for r in result]}):
        names[r[0]] = r[1]
    for r in result:
        r["name"] = names.get(r["student_id"])
    result.sort(key=lambda r: r["name"] or "")
    return {"course_offering_section_id": course_offering_section_id, "threshold": threshold, "results": result}


def apply_correction(db: Session, principal: Principal, obj) -> None:
    """When a correction request is approved, rewrite the attendance mark it refers to."""
    att = db.execute(text("SELECT attendance_id, class_session_id, version FROM student_attendance "
                          "WHERE attendance_id = :a FOR UPDATE"), {"a": obj.attendance_id}).first()
    if att is None:
        raise NotFound("The attendance record no longer exists.")
    if att.version != obj.attendance_version:
        raise Conflict("The attendance record changed after this request was raised.", code="stale_version")
    code = db.execute(text("SELECT status_code FROM attendance_status WHERE attendance_status_id = :i"),
                      {"i": obj.requested_status_id}).scalar()
    policy = db.execute(text("SELECT policy_id FROM class_session WHERE class_session_id = :c"),
                        {"c": att.class_session_id}).scalar()
    credit, denom = policy_weights(db, policy, code)
    db.execute(text("UPDATE student_attendance SET attendance_status_id=:s, credit=:c, denominator=:d, "
                    "version=version+1, marked_by_user_id=:u, marked_at=now() WHERE attendance_id=:a"),
               {"s": obj.requested_status_id, "c": credit, "d": denom, "u": principal.user_id, "a": obj.attendance_id})
    obj.resolved_by_id = principal.user_id
    obj.resolved_at = datetime.now(UTC)

