"""Academic demo content: every teaching / exam persona has real data to work with, and the seeding is idempotent."""
import pytest
from sqlalchemy import text

from app.seed.content_academic import PERSONA_COURSE, TOUCHED, ensure_academic_content

STAFF = [name for name, _ in PERSONA_COURSE]


def counts(db) -> dict[str, int]:
    return {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in TOUCHED}  # noqa: S608 - fixed table names


@pytest.fixture()
def seeded(db):
    ensure_academic_content(db)
    db.flush()
    return db


def listing(client, path: str) -> dict:
    r = client.get(f"{path}?page_size=100")
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"
    return r.json()


def test_seeding_is_idempotent(db):
    before = counts(db)
    first = ensure_academic_content(db)
    db.flush()
    mid = counts(db)
    assert first, "the demo data should be incomplete before the academic content is added"
    assert {t: mid[t] - before[t] for t in TOUCHED if mid[t] != before[t]} == first
    second = ensure_academic_content(db)
    db.flush()
    assert second == {}
    assert counts(db) == mid


@pytest.mark.parametrize("persona", ["teacher", "labinstructor", "coursecoord", "evaluator"])
def test_teaching_personas_see_their_classes_and_assessments(seeded, as_user, persona):
    c = as_user(persona)
    assert listing(c, "/assessments/assessment-event")["count"] > 0
    assert listing(c, "/assessments/student-assessment-mark")["count"] > 0
    if persona != "evaluator":                  # evaluators work on marks only; they hold no attendance permissions
        assert listing(c, "/attendance/class-session")["count"] > 0
        assert listing(c, "/attendance/student-attendance")["count"] > 0
        assert listing(c, "/attendance/lesson-plan-revision")["count"] > 0


@pytest.mark.parametrize("persona", ["mentor", "advisor"])
def test_mentor_and_advisor_have_mentees(seeded, as_user, persona):
    c = as_user(persona)
    assignments = listing(c, "/support/mentor-assignment")
    assert assignments["count"] >= 3
    students = listing(c, "/people/student")
    assert students["count"] >= 3
    assert listing(c, "/support/counselling-session")["count"] >= 3
    mentee_ids = {a["student_id"] for a in assignments["results"]}
    assert mentee_ids <= {s["student_id"] for s in students["results"]}


def test_mentees_are_in_the_mentors_programme_and_sessions_cover_several_states(seeded):
    for username in ("mentor", "advisor"):
        rows = seeded.execute(text(
            "SELECT m.student_id, EXISTS (SELECT 1 FROM student_programme_enrolment e WHERE e.student_id = m.student_id AND e.programme_id IN "
            "(SELECT ura.programme_id FROM user_role_assignment ura WHERE ura.user_id = u.user_id AND ura.programme_id IS NOT NULL)) "
            "FROM user_account u JOIN person_account_link l ON l.user_id = u.user_id JOIN mentor_assignment m ON m.employee_id = l.employee_id "
            "AND m.assignment_status = 'ACTIVE' WHERE u.username = :u"), {"u": username}).all()
        assert len(rows) >= 3 and all(r[1] for r in rows)
        states = {r[0] for r in seeded.execute(text(
            "SELECT cs.session_status FROM counselling_session cs JOIN mentor_assignment m USING (mentor_assignment_id) "
            "JOIN person_account_link l ON l.employee_id = m.employee_id JOIN user_account u ON u.user_id = l.user_id WHERE u.username = :u"),
            {"u": username})}
        assert len(states) >= 3


def test_every_staff_persona_teaches_a_distinct_section_with_a_full_class_record(seeded):
    anchors = {}
    for username in STAFF:
        sections = seeded.execute(text(
            "SELECT DISTINCT f.course_offering_section_id FROM user_account u JOIN person_account_link l ON l.user_id = u.user_id "
            "JOIN faculty_course_assignment f ON f.employee_id = l.employee_id AND f.assignment_status = 'ACTIVE' "
            "WHERE u.username = :u AND EXISTS (SELECT 1 FROM course_offering_section_student r WHERE r.course_offering_section_id = "
            "f.course_offering_section_id AND r.roster_status = 'ACTIVE') ORDER BY 1"), {"u": username}).scalars().all()
        assert sections, f"{username} has no active class with enrolled students"
        anchors[username] = sections[0]
    assert len(set(anchors.values())) == len(anchors), "every persona should have its own section"
    for username, sec in anchors.items():
        q = lambda sql: seeded.execute(text(sql), {"s": sec}).scalar()  # noqa: E731
        assert q("SELECT count(*) FROM timetable_session ts JOIN timetable_revision r ON r.id = ts.revision_id AND r.status = 'PUBLISHED' "
                 "WHERE ts.course_offering_section_id = :s") > 0, username
        assert q("SELECT count(*) FROM class_session WHERE course_offering_section_id = :s") >= 3, username
        assert q("SELECT count(*) FROM class_session WHERE course_offering_section_id = :s AND register_status = 'OPEN'") == 1, username
        assert q("SELECT count(*) FROM class_session WHERE course_offering_section_id = :s AND register_status = 'FINALIZED'") >= 2, username
        assert q("SELECT count(*) FROM student_attendance WHERE course_offering_section_id = :s") > 0, username
        events = {r[0] for r in seeded.execute(text(
            "SELECT e.status FROM assessment_event e JOIN course_offering_section s ON s.course_offering_id = e.course_offering_id "
            "WHERE s.course_offering_section_id = :s"), {"s": sec})}
        assert {"CONDUCTED", "PUBLISHED", "PLANNED"} <= events, (username, events)
        assert q("SELECT count(*) FROM student_assessment_mark m JOIN course_offering_section s ON s.course_offering_id = m.course_offering_id "
                 "WHERE s.course_offering_section_id = :s") > 0, username
        assert q("SELECT count(*) FROM student_course_result x JOIN student_course_registration r USING (course_registration_id) "
                 "JOIN course_offering_section s ON s.course_offering_id = r.course_offering_id WHERE s.course_offering_section_id = :s") > 0, username
        assert q("SELECT count(*) FROM lesson_plan_revision WHERE section_id = :s") > 0, username
        assert q("SELECT count(*) FROM lesson_coverage c JOIN lesson_plan_revision p ON p.id = c.lesson_revision_id WHERE p.section_id = :s") > 0, username
        assert q("SELECT count(*) FROM attendance_correction_request c JOIN student_attendance a USING (attendance_id) "
                 "WHERE a.course_offering_section_id = :s AND c.request_status = 'PENDING'") > 0, username


def test_results_have_published_and_unpublished_rows_and_a_publication_log(seeded):
    states = {r[0] for r in seeded.execute(text("SELECT DISTINCT state FROM student_course_result"))}
    assert {"PUBLISHED", "CALCULATED"} <= states
    unlogged = seeded.execute(text(
        "SELECT count(*) FROM student_course_result r WHERE r.state = 'PUBLISHED' AND NOT EXISTS (SELECT 1 FROM result_publication p "
        "WHERE p.resource = 'student_course_result' AND p.record_id = r.student_course_result_id)")).scalar()
    assert unlogged == 0


@pytest.mark.parametrize("persona", ["student", "student2"])
def test_students_have_timetable_attendance_and_published_results(seeded, as_user, persona):
    c = as_user(persona)
    tt = c.get("/timetable/mine?on=2026-10-12")
    assert tt.status_code == 200, tt.text
    sessions = [item for day in tt.json()["sessions"] for item in day["items"]]
    assert len(sessions) >= 6
    results = listing(c, "/assessments/student-course-result")
    assert results["count"] > 0 and all(r["state"] == "PUBLISHED" for r in results["results"])
    assert listing(c, "/attendance/student-attendance")["count"] > 0


@pytest.mark.parametrize("persona", ["examcell", "examofficer", "resultapprover", "registrar"])
def test_exam_personas_see_results(seeded, as_user, persona):
    c = as_user(persona)
    r = c.get("/assessments/student-course-result?page_size=100")
    if persona == "registrar":                  # the registrar's role does not carry results; only check it is not an error page
        assert r.status_code in (200, 403)
        return
    assert r.status_code == 200, r.text
    assert r.json()["count"] > 0
    assert {x["state"] for x in r.json()["results"]} >= {"PUBLISHED", "CALCULATED"} or persona == "resultapprover"


@pytest.mark.parametrize("persona", ["hod", "ttcoord", "progcoord", "semcoord"])
def test_department_and_programme_staff_see_the_teaching_setup(seeded, as_user, persona):
    c = as_user(persona)
    assert listing(c, "/timetable/faculty-course-assignment")["count"] > 0 or persona in ("progcoord", "semcoord")
    assert listing(c, "/timetable/timetable-session")["count"] > 0
    assert listing(c, "/registration/course-offering-section")["count"] > 0
    if persona == "hod":
        assert listing(c, "/assessments/student-course-result")["count"] > 0
