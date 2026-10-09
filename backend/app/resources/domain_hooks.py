"""Domain side effects and integrity rules that go beyond field validation. Imported once by the registry."""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.rbac.engine import Principal
from app.resources import rules
from app.worker.queue import enqueue

AFTER_UPDATE: dict[str, list] = {}


def after_update(table: str):
    def deco(fn):
        AFTER_UPDATE.setdefault(table, []).append(fn)
        return fn
    return deco


def run_after_update(spec, db: Session, principal: Principal, obj: Any) -> None:
    for fn in AFTER_UPDATE.get(spec.table, []):
        fn(db, principal, obj)


# ------------------------------------------------------------------------------------------------- timetable
def _check_clashes(db: Session, principal: Principal, obj: Any) -> None:
    """A room, a teacher or a class section can only be in one place at a time within a timetable revision."""
    rows = db.execute(text(
        "SELECT o.timetable_session_id, "
        "(o.room_id IS NOT NULL AND o.room_id = n.room_id) AS room, "
        "(f1.employee_id IS NOT NULL AND f1.employee_id = f2.employee_id) AS teacher, "
        "(s1.class_section_id = s2.class_section_id AND (s1.class_batch_id IS NULL OR s2.class_batch_id IS NULL "
        "  OR s1.class_batch_id = s2.class_batch_id)) AS section "
        "FROM timetable_session n "
        "JOIN timetable_session o ON o.revision_id = n.revision_id AND o.timetable_session_id <> n.timetable_session_id "
        "  AND o.day_of_week = n.day_of_week AND o.time_slot_id = n.time_slot_id "
        "  AND o.effective_from <= n.effective_to AND n.effective_from <= o.effective_to "
        "JOIN course_offering_section s1 ON s1.course_offering_section_id = o.course_offering_section_id "
        "JOIN course_offering_section s2 ON s2.course_offering_section_id = n.course_offering_section_id "
        "LEFT JOIN faculty_course_assignment f1 ON f1.faculty_assignment_id = o.faculty_assignment_id "
        "LEFT JOIN faculty_course_assignment f2 ON f2.faculty_assignment_id = n.faculty_assignment_id "
        "WHERE n.timetable_session_id = :n"), {"n": obj.timetable_session_id}).all()
    for r in rows:
        what = "room" if r.room else "teacher" if r.teacher else "class section" if r.section else None
        if what:
            raise Conflict(f"Clash: the {what} is already scheduled at this time (session #{r.timetable_session_id}).",
                           code="timetable_clash", details={"conflicts_with": r.timetable_session_id, "resource": what})


@rules.after_create("timetable_session")
def _tt_create(db, principal, obj):
    _check_clashes(db, principal, obj)


@after_update("timetable_session")
def _tt_update(db, principal, obj):
    _check_clashes(db, principal, obj)


# ------------------------------------------------------------------------------------------- transition hooks
def certificate_issued(db: Session, principal: Principal, obj: Any) -> None:
    obj.issued_at = datetime.now(UTC)
    if not obj.certificate_number:
        obj.certificate_number = rules.next_number(db, "certificate_request", "certificate_number",
                                                   f"CERT-{rules.today().year}-")
    _notify_student(db, obj.student_id, "Your certificate is ready", f"Certificate {obj.certificate_number} has been issued.",
                    "/r/documents/certificate-request/" + str(obj.certificate_request_id))


def grievance_log(action: str):
    def after(db: Session, principal: Principal, obj: Any) -> None:
        db.execute(text("INSERT INTO grievance_action (grievance_id, action_type, new_status, action_at, action_notes) "
                        "VALUES (:g, :a, :s, now(), :n)"),
                   {"g": obj.grievance_id, "a": action.upper(), "s": obj.status, "n": f"By user {principal.user_id}"})
        if obj.status in ("RESOLVED", "REJECTED"):
            obj.resolved_at = datetime.now(UTC)
        _notify_student(db, obj.student_id, f"Grievance {obj.grievance_number}: {obj.status.replace('_', ' ').lower()}",
                        None, "/r/support/grievance/" + str(obj.grievance_id))
    return after


def announcement_approved(db: Session, principal: Principal, obj: Any) -> None:
    enqueue(db, "announcement.deliver", {"announcement_id": obj.announcement_id},
            dedupe_key=f"announcement:{obj.announcement_id}", user_id=principal.user_id)


def _notify_student(db: Session, student_id: int | None, title: str, body: str | None, link: str) -> None:
    if student_id is None:
        return
    uids = [u for (u,) in db.execute(text("SELECT user_id FROM person_account_link WHERE student_id = :s"), {"s": student_id})]
    if uids:
        enqueue(db, "notify.users", {"user_ids": uids, "title": title, "body": body, "link": link})


def deliver_announcement(db: Session, announcement_id: int) -> int:
    """Fan an approved announcement out to its audience as in-app notifications."""
    a = db.execute(text("SELECT title, audience_type, institution_id, department_id FROM announcement WHERE announcement_id = :a"),
                   {"a": announcement_id}).first()
    if a is None:
        return 0
    kind = a.audience_type
    if kind == "CUSTOM":
        q, p = "SELECT user_id FROM announcement_user_target WHERE announcement_id = :a", {"a": announcement_id}
    elif kind == "PROGRAMME":
        q = ("SELECT DISTINCT l.user_id FROM announcement_programme_target t "
             "JOIN student_programme_enrolment e ON e.programme_id = t.programme_id AND e.enrolment_status = 'ACTIVE' "
             "JOIN person_account_link l ON l.student_id = e.student_id WHERE t.announcement_id = :a")
        p = {"a": announcement_id}
    elif kind == "STUDENTS":
        q = ("SELECT l.user_id FROM person_account_link l JOIN student s ON s.student_id = l.student_id "
             "WHERE s.student_status = 'ACTIVE' AND s.institution_id = :i")
        p = {"i": a.institution_id}
    elif kind == "STAFF":
        q = ("SELECT l.user_id FROM person_account_link l JOIN employee e ON e.employee_id = l.employee_id "
             "WHERE e.employment_status = 'ACTIVE' AND e.institution_id = :i")
        p = {"i": a.institution_id}
    elif kind == "DEPARTMENT":
        q = ("SELECT l.user_id FROM person_account_link l JOIN employee_assignment ea ON ea.employee_id = l.employee_id "
             "AND ea.end_date IS NULL WHERE ea.department_id = :d UNION "
             "SELECT l.user_id FROM person_account_link l JOIN student s ON s.student_id = l.student_id WHERE s.department_id = :d")
        p = {"d": a.department_id}
    else:  # ALL
        q, p = "SELECT user_id FROM user_account WHERE is_active", {}
    users = [u for (u,) in db.execute(text(q), p)]
    for i in range(0, len(users), 500):
        enqueue(db, "notify.users", {"user_ids": users[i:i + 500], "title": a.title[:200], "body": "New announcement",
                                     "link": f"/r/communication/announcement/{announcement_id}"})
    return len(users)
