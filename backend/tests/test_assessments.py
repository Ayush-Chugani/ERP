"""Marks entry, grade calculation, publication and what students are allowed to see."""
import pytest
from sqlalchemy import text


@pytest.fixture()
def offering(db):
    row = db.execute(text(
        "SELECT o.course_offering_id, e.assessment_event_id, e.maximum_marks FROM course_offering o "
        "JOIN assessment_event e ON e.course_offering_id = o.course_offering_id AND e.status = 'CONDUCTED' "
        "WHERE EXISTS (SELECT 1 FROM student_assessment_mark m WHERE m.assessment_event_id = e.assessment_event_id) "
        "AND o.course_offering_id IN (SELECT s.course_offering_id FROM course_offering_section s JOIN faculty_course_assignment fa "
        "ON fa.course_offering_section_id = s.course_offering_section_id JOIN person_account_link l ON l.employee_id = fa.employee_id "
        "JOIN user_account u ON u.user_id = l.user_id WHERE u.username = 'teacher') "
        "ORDER BY 1 LIMIT 1")).first()
    if row is None:
        pytest.skip("no conducted assessment in demo data")
    return row


def test_marks_entry_validation(as_user, offering, db):
    off, event, maxm = offering
    regs = [r[0] for r in db.execute(text(
        "SELECT course_registration_id FROM student_course_registration WHERE course_offering_id=:o ORDER BY 1 LIMIT 2"), {"o": off})]
    teacher = as_user("teacher")
    url = f"/assessments/events/{event}/marks"
    ok = teacher.put(url, json={"marks": [{"course_registration_id": regs[0], "marks_obtained": "40"},
                                          {"course_registration_id": regs[1], "attendance_status": "ABSENT"}]})
    assert ok.status_code == 200 and ok.json()["saved"] == 2, ok.text
    over = teacher.put(url, json={"marks": [{"course_registration_id": regs[0], "marks_obtained": str(float(maxm) + 1)}]})
    assert over.status_code == 422
    assert teacher.put(url, json={"marks": [{"course_registration_id": regs[0]}]}).status_code == 422       # marks missing
    assert teacher.put(url, json={"marks": [{"course_registration_id": 99999999, "marks_obtained": "1"}]}).status_code == 422
    assert teacher.put(url, json={"marks": [{"course_registration_id": regs[0], "attendance_status": "ABSENT",
                                             "marks_obtained": "5"}]}).status_code == 422
    assert as_user("student").put(url, json={"marks": [{"course_registration_id": regs[0], "marks_obtained": "40"}]}).status_code in (403, 404)


def test_calculate_publish_and_student_visibility(as_user, offering, db):
    off, event, _ = offering
    exam = as_user("examcell")
    r = exam.post(f"/assessments/offerings/{off}/calculate-results")
    assert r.status_code == 200, r.text
    assert r.json()["calculated"] > 0
    results = exam.get("/assessments/student-course-result?page_size=100").json()["results"]
    assert results and all(x["state"] == "CALCULATED" for x in results[:5])
    assert all(x["grade_letter"] for x in results if x["result_status"] in ("PASS", "FAIL"))
    # a student cannot see unpublished results
    student_user = db.execute(text(
        "SELECT u.username FROM student_course_result res JOIN student_course_registration r USING (course_registration_id) "
        "JOIN student_term_registration t USING (term_registration_id) JOIN student_programme_enrolment e USING (enrolment_id) "
        "JOIN person_account_link l ON l.student_id = e.student_id JOIN user_account u ON u.user_id = l.user_id LIMIT 1")).scalar()
    assert student_user, "a registered student with a login is needed"
    student = as_user(student_user)
    assert student.get("/assessments/student-course-result").json()["count"] == 0
    target = next(x for x in results if x["course_registration_id"] in [r_[0] for r_ in db.execute(text(
        "SELECT r.course_registration_id FROM student_course_registration r JOIN student_term_registration t USING (term_registration_id) "
        "JOIN student_programme_enrolment e USING (enrolment_id) JOIN person_account_link l ON l.student_id = e.student_id "
        "JOIN user_account u ON u.user_id = l.user_id WHERE u.username = :n"), {"n": student_user})])
    rid = target["student_course_result_id"]
    assert student.post(f"/assessments/student-course-result/{rid}/actions/publish").status_code == 403
    assert exam.post(f"/assessments/student-course-result/{rid}/actions/publish").status_code == 200
    mine = student.get("/assessments/student-course-result").json()
    assert mine["count"] == 1 and mine["results"][0]["student_course_result_id"] == rid
    # a published result is not silently recalculated
    again = exam.post(f"/assessments/offerings/{off}/calculate-results").json()
    assert again["skipped_published"] >= 1
    assert exam.post(f"/assessments/student-course-result/{rid}/actions/withhold").status_code == 422     # remarks required
    assert exam.post(f"/assessments/student-course-result/{rid}/actions/withhold", json={"remarks": "Under review"}).status_code == 200
    assert student.get("/assessments/student-course-result").json()["count"] == 0


def test_term_result_and_transcript(as_user, offering, db):
    off, _, _ = offering
    exam = as_user("examcell")
    exam.post(f"/assessments/offerings/{off}/calculate-results")
    term = db.execute(text("SELECT term_registration_id FROM student_course_registration WHERE course_offering_id=:o LIMIT 1"), {"o": off}).scalar()
    r = exam.post(f"/assessments/term-registrations/{term}/calculate-term-result")
    assert r.status_code in (200, 409), r.text
    if r.status_code == 200:
        body = r.json()
        assert body["sgpa"] is None or 0 <= float(body["sgpa"]) <= 10
    sid = db.execute(text("SELECT e.student_id FROM student_term_registration t JOIN student_programme_enrolment e USING (enrolment_id) WHERE t.term_registration_id=:t"), {"t": term}).scalar()
    assert exam.get(f"/assessments/transcript/{sid}").status_code == 200
