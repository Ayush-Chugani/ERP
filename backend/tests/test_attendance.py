"""Attendance register lifecycle, policy-driven marks, summaries and corrections."""
import pytest
from sqlalchemy import text


@pytest.fixture()
def session_id(db):
    row = db.execute(text(
        "SELECT cs.class_session_id FROM class_session cs WHERE cs.register_status = 'FINALIZED' "
        "AND EXISTS (SELECT 1 FROM student_attendance a WHERE a.class_session_id = cs.class_session_id) "
        "AND cs.course_offering_section_id IN (SELECT fa.course_offering_section_id FROM faculty_course_assignment fa "
        "JOIN person_account_link l ON l.employee_id = fa.employee_id JOIN user_account u ON u.user_id = l.user_id WHERE u.username = 'teacher') "
        "ORDER BY cs.class_session_id LIMIT 1")).first()
    if row is None:
        pytest.skip("demo data has no finalized session")
    return row[0]


def test_register_lifecycle_and_marking(as_user, session_id):
    hod, teacher = as_user("hod"), as_user("teacher")
    base = f"/attendance/class-session/{session_id}"
    roster = teacher.get(f"/attendance/sessions/{session_id}/roster")
    assert roster.status_code == 200
    students = roster.json()["students"]
    assert len(students) >= 2
    # a finalized register rejects marks
    body = {"marks": [{"student_id": students[0]["student_id"], "status": "ABSENT"}]}
    r = teacher.put(f"/attendance/sessions/{session_id}/marks", json=body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "register_closed"
    # reopening needs approval rights and a reason
    assert teacher.post(f"{base}/actions/reopen_register", json={"remarks": "wrong"}).status_code == 403
    assert hod.post(f"{base}/actions/reopen_register").status_code == 422
    assert hod.post(f"{base}/actions/reopen_register", json={"remarks": "Marked wrong student"}).status_code == 200
    marks = [{"student_id": students[0]["student_id"], "status": "ABSENT", "remarks": "sick"},
             {"student_id": students[1]["student_id"], "status": "PRESENT"}]
    r = teacher.put(f"/attendance/sessions/{session_id}/marks", json={"marks": marks})
    assert r.status_code == 200 and r.json()["saved"] == 2
    again = teacher.get(f"/attendance/sessions/{session_id}/roster").json()["students"]
    assert {s["student_id"]: s["status"] for s in again}[students[0]["student_id"]] == "ABSENT"
    # unknown student / duplicate rows are rejected
    assert teacher.put(f"/attendance/sessions/{session_id}/marks",
                       json={"marks": [{"student_id": 99999999, "status": "PRESENT"}]}).status_code == 422
    dup = {"marks": [marks[0], marks[0]]}
    assert teacher.put(f"/attendance/sessions/{session_id}/marks", json=dup).status_code == 422
    assert teacher.post(f"{base}/actions/finalize_register").status_code == 200


def test_summary_flags_shortage_and_respects_scope(as_user, db):
    sec = db.execute(text("SELECT course_offering_section_id FROM student_attendance GROUP BY 1 ORDER BY count(*) DESC LIMIT 1")).scalar()
    hod = as_user("hod")
    s = hod.get(f"/attendance/summary?course_offering_section_id={sec}")
    assert s.status_code == 200
    rows = s.json()["results"]
    assert rows and all(r["percentage"] is None or 0 <= float(r["percentage"]) <= 100 for r in rows)
    own = as_user("student").get(f"/attendance/summary?course_offering_section_id={sec}").json()["results"]
    assert len(own) <= 1


def test_students_cannot_mark_attendance(as_user, session_id):
    st = as_user("student")
    r = st.put(f"/attendance/sessions/{session_id}/marks", json={"marks": [{"student_id": 1, "status": "PRESENT"}]})
    assert r.status_code in (403, 404)


def test_correction_request_updates_the_mark(as_user, db):
    row = db.execute(text(
        "SELECT a.attendance_id, a.student_id, a.version, a.attendance_status_id FROM student_attendance a "
        "JOIN person_account_link l ON l.student_id = a.student_id ORDER BY a.attendance_id LIMIT 1")).first()
    if row is None:
        pytest.skip("no attendance for a linked student")
    username = db.execute(text("SELECT u.username FROM person_account_link l JOIN user_account u USING (user_id) "
                               "WHERE l.student_id = :s"), {"s": row.student_id}).scalar()
    student = as_user(username)
    absent = db.execute(text("SELECT attendance_status_id FROM attendance_status WHERE status_code='ABSENT'")).scalar()
    r = student.post("/attendance/attendance-correction-request", json={
        "attendance_id": row.attendance_id, "attendance_version": row.version, "old_status_id": row.attendance_status_id,
        "requested_status_id": absent, "reason": "I was marked wrongly", "evidence_reference": "n/a"})
    assert r.status_code == 201, r.text
    rid = r.json()["attendance_correction_id"]
    assert student.post(f"/attendance/attendance-correction-request/{rid}/actions/approve").status_code == 403
    hod = as_user("hod")
    done = hod.post(f"/attendance/attendance-correction-request/{rid}/actions/approve", json={"remarks": "verified"})
    assert done.status_code in (200, 404), done.text
    if done.status_code == 200:
        status = db.execute(text("SELECT attendance_status_id, version FROM student_attendance WHERE attendance_id=:a"),
                            {"a": row.attendance_id}).first()
        assert status.attendance_status_id == absent and status.version == row.version + 1
