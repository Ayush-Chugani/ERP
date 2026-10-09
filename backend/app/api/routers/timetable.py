"""Personal timetable: what the signed-in student or teacher is scheduled to attend or teach (published revisions only)."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import active_principal
from app.db.session import get_db
from app.rbac.engine import Principal

router = APIRouter(prefix="/timetable", tags=["Timetable"])
DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

_SELECT = (
    "SELECT ts.timetable_session_id, ts.day_of_week, sl.start_time, sl.end_time, c.course_code, c.course_title, "
    "o.offering_code, r.room_code, ts.effective_from, ts.effective_to, f.display_name AS faculty "
    "FROM timetable_session ts "
    "JOIN timetable_revision rev ON rev.id = ts.revision_id AND rev.status = 'PUBLISHED' "
    "JOIN time_slot sl ON sl.time_slot_id = ts.time_slot_id "
    "JOIN course_offering_section s ON s.course_offering_section_id = ts.course_offering_section_id "
    "JOIN course_offering o ON o.course_offering_id = s.course_offering_id JOIN course_catalog c ON c.course_id = o.course_id "
    "LEFT JOIN room r ON r.room_id = ts.room_id "
    "LEFT JOIN faculty_course_assignment fa ON fa.faculty_assignment_id = ts.faculty_assignment_id "
    "LEFT JOIN employee f ON f.employee_id = fa.employee_id "
    "WHERE :on BETWEEN ts.effective_from AND ts.effective_to AND ({who}) ORDER BY ts.day_of_week, sl.start_time"
)


@router.get("/mine")
def my_timetable(on: date | None = Query(default=None, description="Date to show (default today)"),
                 principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Weekly timetable as seen by the signed-in person. Students: the sections they are enrolled in. Staff: their teaching."""
    day = on or date.today()
    clauses, params = [], {"on": day}
    if principal.student_ids:
        clauses.append("EXISTS (SELECT 1 FROM course_offering_section_student rs JOIN student_course_registration cr "
                       "ON cr.course_registration_id = rs.course_registration_id JOIN student_term_registration t "
                       "ON t.term_registration_id = cr.term_registration_id JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
                       "WHERE rs.course_offering_section_id = ts.course_offering_section_id AND rs.roster_status = 'ACTIVE' "
                       "AND e.student_id = ANY(:students))")
        params["students"] = list(principal.student_ids)
    if principal.employee_ids:
        clauses.append("fa.employee_id = ANY(:employees)")
        params["employees"] = list(principal.employee_ids)
    if not clauses:
        return {"date": day, "sessions": []}
    rows = db.execute(text(_SELECT.format(who=" OR ".join(clauses))), params).mappings().all()
    days: dict[int, list] = {d: [] for d in range(1, 8)}
    for r in rows:
        days[r["day_of_week"]].append({
            "session_id": r["timetable_session_id"], "start": r["start_time"], "end": r["end_time"], "course_code": r["course_code"],
            "course": r["course_title"], "offering": r["offering_code"], "room": r["room_code"], "faculty": r["faculty"]})
    return {"date": day, "sessions": [{"day": DAYS[d - 1], "day_number": d, "items": items} for d, items in days.items() if items]}
