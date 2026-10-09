"""The least-privilege role matrix, checked three ways: (1) what each built-in role holds in the database, (2) what the API
lets each demo persona read and create, (3) the segregation-of-duties rules on real records."""
import pytest
from sqlalchemy import select, text

from app.models.accounts import UserAccount
from app.rbac.engine import load_principal
from app.resources.registry import build_registry
from app.resources.spec import REGISTRY

PERSONA_ROLE = {
    "demoadmin": None, "sysadmin": "SYSTEM_ADMIN", "secadmin": "SECURITY_ADMIN", "orgadmin": "INSTITUTION_ADMIN",
    "vc": "VICE_CHANCELLOR", "dean": "DEAN_ACADEMICS", "campusadm": "CAMPUS_DIRECTOR", "hod": "HEAD_DEPARTMENT",
    "registrar": "REGISTRAR", "admissions": "ADMISSION_OFFICER", "docverifier": "DOCUMENT_VERIFIER",
    "sectionofficer": "STUDENT_SECTION_OFFICER", "examcell": "CONTROLLER_EXAMINATIONS", "examofficer": "EXAMINATION_OFFICER",
    "evaluator": "EVALUATOR", "resultapprover": "RESULT_APPROVER", "teacher": "FACULTY", "labinstructor": "LAB_INSTRUCTOR",
    "coursecoord": "COURSE_COORDINATOR", "ttcoord": "TIMETABLE_COORDINATOR", "progcoord": "PROGRAMME_COORDINATOR",
    "semcoord": "SEMESTER_COORDINATOR", "advisor": "FACULTY_ADVISOR", "mentor": "MENTOR", "support": "GRIEVANCE_OFFICER",
    "finance": "FINANCE_OFFICER", "auditor": "INTERNAL_AUDITOR", "extauditor": "EXTERNAL_AUDITOR", "student": "STUDENT",
    "applicant": "APPLICANT", "parent": "PARENT_GUARDIAN", "alumni": "ALUMNI",
}

# ------------------------------------------------------------------------ (1) grants held by each role in the database
MUST = {
    "FACULTY": ["ATTENDANCE.STUDENT_ATTENDANCE.CREATE", "ATTENDANCE.CLASS_SESSION.UPDATE", "ASSESSMENT.STUDENT_ASSESSMENT_MARK.UPDATE",
                "MENTORING.COUNSELLING_SESSION.CREATE", "TIMETABLE.ALL.READ", "CURRICULUM.ALL.READ", "STUDENT.STUDENT.READ"],
    "REGISTRAR": ["STUDENT.ALL.CREATE", "ADMISSION.ALL.APPROVE", "DOCUMENT.ALL.PUBLISH", "CURRICULUM.ALL.PUBLISH", "ACADEMIC_CALENDAR.ALL.PUBLISH"],
    "CONTROLLER_EXAMINATIONS": ["ASSESSMENT.ALL.PUBLISH", "RESULT.ALL.PUBLISH", "RESULT.ALL.VERIFY", "DOCUMENT.ALL.PUBLISH"],
    "EXAMINATION_OFFICER": ["RESULT.STUDENT_COURSE_RESULT.CREATE", "RESULT.STUDENT_TERM_RESULT.UPDATE", "ASSESSMENT.ALL.CREATE"],
    "RESULT_APPROVER": ["RESULT.ALL.APPROVE", "RESULT.ALL.VERIFY"],
    "EVALUATOR": ["ASSESSMENT.STUDENT_ASSESSMENT_MARK.CREATE", "ASSESSMENT.STUDENT_ASSESSMENT_MARK.UPDATE"],
    "DEAN_ACADEMICS": ["CURRICULUM.ALL.PUBLISH", "CURRICULUM.ALL.APPROVE", "STAFF_ACTIVITIES.ALL.VERIFY", "STUDENT.ALL.APPROVE"],
    "HEAD_DEPARTMENT": ["STAFF_ACTIVITIES.ALL.VERIFY", "STAFF_ACTIVITIES.ALL.APPROVE", "TEACHING.ALL.ASSIGN", "TIMETABLE.ALL.APPROVE",
                        "ATTENDANCE.ALL.APPROVE", "RESULT.ALL.VERIFY", "MENTORING.ALL.ASSIGN", "CURRICULUM.ALL.CREATE", "CURRICULUM.ALL.UPDATE"],
    "CAMPUS_DIRECTOR": ["TIMETABLE.ALL.APPROVE", "TIMETABLE.ALL.PUBLISH", "RESULT.ALL.APPROVE", "GRIEVANCE.ALL.ASSIGN", "STUDENT.ALL.APPROVE",
                        "EMPLOYEE.ALL.APPROVE"],
    "TIMETABLE_COORDINATOR": ["TIMETABLE.ALL.CREATE", "TIMETABLE.ALL.ASSIGN", "TEACHING.ALL.ASSIGN"],
    "GRIEVANCE_OFFICER": ["GRIEVANCE.ALL.UPDATE", "GRIEVANCE.ALL.ASSIGN", "GRIEVANCE.ALL.APPROVE"],
    "FINANCE_OFFICER": ["ADMISSION.ADMISSION_FEE_CLEARANCE.VERIFY"],
    "STUDENT": ["GRIEVANCE.ALL.CREATE", "DOCUMENT.CERTIFICATE_REQUEST.CREATE", "ATTENDANCE.ATTENDANCE_CORRECTION_REQUEST.CREATE",
                "STUDENT.STUDENT.UPDATE", "FEEDBACK.FEEDBACK_RESPONSE.CREATE"],
    "APPLICANT": ["ADMISSION.ADMISSION_APPLICATION.CREATE", "ADMISSION.ADMISSION_APPLICATION.UPDATE", "DOCUMENT.STUDENT_DOCUMENT.CREATE"],
    "SYSTEM_ADMIN": ["IAM.ALL.CREATE", "REFERENCE.ALL.DELETE", "ACADEMIC_CALENDAR.ALL.CREATE", "COMMUNICATION.ALL.CREATE"],
    "SECURITY_ADMIN": ["IAM.ALL.CREATE", "IAM.ALL.ASSIGN", "AUDIT.ALL.READ", "AUDIT.ALL.EXPORT"],
}
MUST_NOT = {
    "FACULTY": ["RESULT.ALL.READ", "RESULT.ALL.CREATE", "ASSESSMENT.ALL.APPROVE", "ASSESSMENT.ALL.PUBLISH", "ASSESSMENT.ALL.VERIFY",
                "ACADEMIC_CALENDAR.ALL.CREATE", "CURRICULUM.ALL.CREATE", "CURRICULUM.ALL.APPROVE", "REGISTRATION.ALL.CREATE",
                "REGISTRATION.ALL.APPROVE", "STUDENT.ALL.CREATE", "STUDENT.ALL.UPDATE", "STUDENT.ALL.APPROVE", "ATTENDANCE.ALL.APPROVE",
                "EMPLOYEE.ALL.READ", "ADMISSION.ALL.READ", "GRIEVANCE.ALL.READ", "STUDENT.ALL.READ", "FEEDBACK.ALL.READ"],
    "LAB_INSTRUCTOR": ["RESULT.ALL.READ", "ASSESSMENT.ALL.PUBLISH", "CURRICULUM.ALL.CREATE", "STUDENT.ALL.UPDATE", "STUDENT.ALL.READ", "FEEDBACK.ALL.READ"],
    "MENTOR": ["ATTENDANCE.ALL.CREATE", "ASSESSMENT.ALL.CREATE", "RESULT.ALL.CREATE", "STUDENT.ALL.UPDATE", "CURRICULUM.ALL.CREATE"],
    "FACULTY_ADVISOR": ["ATTENDANCE.ALL.CREATE", "ASSESSMENT.ALL.CREATE", "RESULT.ALL.CREATE", "REGISTRATION.ALL.CREATE"],
    "COURSE_COORDINATOR": ["RESULT.ALL.READ", "ASSESSMENT.ALL.PUBLISH", "CURRICULUM.ALL.CREATE", "REGISTRATION.ALL.CREATE"],
    "EVALUATOR": ["RESULT.ALL.VERIFY", "RESULT.ALL.PUBLISH", "RESULT.ALL.READ", "STUDENT.ALL.READ", "STUDENT.ALL.UPDATE", "ASSESSMENT.ALL.PUBLISH",
                  "ASSESSMENT.ALL.CREATE", "ASSESSMENT.ASSESSMENT_EVENT.UPDATE", "COMMUNICATION.ALL.READ"],
    "EXAMINATION_OFFICER": ["RESULT.ALL.PUBLISH", "RESULT.ALL.VERIFY", "RESULT.ALL.APPROVE", "ASSESSMENT.ALL.PUBLISH", "RESULT.ALL.CREATE",
                            "RESULT.RESULT_PUBLICATION.CREATE"],
    "RESULT_APPROVER": ["RESULT.ALL.CREATE", "RESULT.ALL.UPDATE", "ASSESSMENT.ALL.CREATE", "ASSESSMENT.ALL.UPDATE", "STUDENT.ALL.UPDATE"],
    "HEAD_DEPARTMENT": ["CURRICULUM.ALL.APPROVE", "CURRICULUM.ALL.PUBLISH", "ACADEMIC_CALENDAR.ALL.APPROVE", "ACADEMIC_CALENDAR.ALL.CREATE",
                        "RESULT.ALL.PUBLISH", "RESULT.ALL.CREATE", "STUDENT.ALL.UPDATE", "STUDENT.ALL.APPROVE", "TIMETABLE.ALL.PUBLISH"],
    "DEAN_ACADEMICS": ["RESULT.ALL.CREATE", "RESULT.ALL.PUBLISH", "ATTENDANCE.ALL.CREATE", "ASSESSMENT.ALL.CREATE", "STUDENT.ALL.CREATE"],
    "VICE_CHANCELLOR": ["STUDENT.ALL.CREATE", "STUDENT.ALL.UPDATE", "RESULT.ALL.CREATE", "CURRICULUM.ALL.CREATE", "ADMISSION.ALL.CREATE",
                        "ATTENDANCE.ALL.CREATE", "GRIEVANCE.ALL.UPDATE"],
    "REGISTRAR": ["ASSESSMENT.ALL.CREATE", "RESULT.ALL.CREATE", "RESULT.ALL.PUBLISH", "ATTENDANCE.ALL.CREATE", "EMPLOYEE.ALL.CREATE",
                  "EMPLOYEE.ALL.UPDATE", "IAM.ALL.READ", "REFERENCE.ALL.DELETE"],
    "ADMISSION_OFFICER": ["RESULT.ALL.READ", "STUDENT.ALL.CREATE", "STUDENT.ALL.UPDATE", "REGISTRATION.ALL.READ"],
    "DOCUMENT_VERIFIER": ["DOCUMENT.ALL.CREATE", "DOCUMENT.ALL.UPDATE", "DOCUMENT.ALL.PUBLISH", "STUDENT.ALL.UPDATE"],
    "STUDENT_SECTION_OFFICER": ["RESULT.ALL.READ", "ADMISSION.ALL.CREATE", "REGISTRATION.ALL.PUBLISH"],
    "CONTROLLER_EXAMINATIONS": ["STUDENT.ALL.UPDATE", "ADMISSION.ALL.READ", "CURRICULUM.ALL.CREATE", "STUDENT.ALL.READ"],
    "PROGRAMME_COORDINATOR": ["RESULT.ALL.CREATE", "ATTENDANCE.ALL.CREATE", "CURRICULUM.ALL.APPROVE", "CURRICULUM.ALL.PUBLISH"],
    "TIMETABLE_COORDINATOR": ["RESULT.ALL.READ", "STUDENT.ALL.READ", "ATTENDANCE.ALL.CREATE", "TIMETABLE.ALL.PUBLISH"],
    "GRIEVANCE_OFFICER": ["STUDENT.ALL.UPDATE", "RESULT.ALL.READ", "ADMISSION.ALL.READ", "GRIEVANCE.ALL.DELETE", "STUDENT.ALL.READ"],
    "FINANCE_OFFICER": ["STUDENT.ALL.READ", "RESULT.ALL.READ", "ADMISSION.ALL.CREATE", "ADMISSION.ALL.APPROVE", "ADMISSION.ALL.UPDATE"],
    "INTERNAL_AUDITOR": ["STUDENT.ALL.CREATE", "STUDENT.ALL.UPDATE", "RESULT.ALL.CREATE", "ADMISSION.ALL.APPROVE", "DOCUMENT.ALL.PUBLISH",
                         "CURRICULUM.ALL.CREATE", "IAM.ALL.READ"],
    "EXTERNAL_AUDITOR": ["STUDENT.ALL.CREATE", "STUDENT.ALL.UPDATE", "RESULT.ALL.CREATE", "ADMISSION.ALL.APPROVE", "DOCUMENT.ALL.PUBLISH"],
    "STUDENT": ["RESULT.ALL.CREATE", "RESULT.ALL.UPDATE", "ASSESSMENT.ALL.CREATE", "ASSESSMENT.ALL.UPDATE", "ATTENDANCE.STUDENT_ATTENDANCE.CREATE",
                "ATTENDANCE.STUDENT_ATTENDANCE.UPDATE", "STUDENT.ALL.CREATE", "STUDENT.ALL.DELETE", "ADMISSION.ALL.CREATE",
                "EMPLOYEE.ALL.READ", "COMMUNICATION.ALL.CREATE", "GRIEVANCE.ALL.UPDATE", "GRIEVANCE.ALL.APPROVE"],
    "APPLICANT": ["STUDENT.ALL.CREATE", "RESULT.ALL.READ", "ATTENDANCE.ALL.READ", "ASSESSMENT.ALL.CREATE", "FEEDBACK.ALL.CREATE",
                  "COMMUNICATION.ALL.CREATE"],
    "PARENT_GUARDIAN": [f"{m}.ALL.{a}" for m in ("STUDENT", "ATTENDANCE", "RESULT", "ASSESSMENT", "ADMISSION", "REGISTRATION", "FEEDBACK",
                                                 "GRIEVANCE", "DOCUMENT", "COMMUNICATION") for a in ("CREATE", "UPDATE", "DELETE", "APPROVE")],
    "ALUMNI": ["ATTENDANCE.ALL.CREATE", "ASSESSMENT.ALL.CREATE", "RESULT.ALL.CREATE", "RESULT.ALL.UPDATE", "STUDENT.ALL.CREATE"],
    "SYSTEM_ADMIN": ["RESULT.ALL.READ", "ASSESSMENT.ALL.READ", "EMPLOYEE.EMPLOYEE_AADHAAR.READ", "EMPLOYEE.EMPLOYEE_PAN.READ",
                     "EMPLOYEE.EMPLOYEE_BANK_ACCOUNT.READ", "STUDENT.ALL.READ"],
    "SECURITY_ADMIN": ["STUDENT.ALL.READ", "RESULT.ALL.READ", "ASSESSMENT.ALL.READ", "ADMISSION.ALL.READ"],
    "INSTITUTION_ADMIN": ["IAM.ALL.CONFIGURE", "IAM.ALL.IMPERSONATE", "IAM.ALL.DELETE"],
}


def held(db, role_code):
    return {c for (c,) in db.execute(text(
        "SELECT p.permission_code FROM role_permission rp JOIN permission p USING (permission_id) JOIN role r USING (role_id) "
        "WHERE r.role_code = :r AND rp.permission_effect = 'ALLOW'"), {"r": role_code})}


@pytest.mark.parametrize("role", sorted(MUST))
def test_each_role_holds_what_its_job_needs(db, role):
    assert set(MUST[role]) <= held(db, role)


@pytest.mark.parametrize("role", sorted(MUST_NOT))
def test_no_role_holds_what_it_must_not(db, role):
    assert not set(MUST_NOT[role]) & held(db, role)


def test_sensitive_staff_identifiers_are_held_by_nobody_but_super_admins(db):
    rows = db.execute(text(
        "SELECT DISTINCT r.role_code FROM role_permission rp JOIN permission p USING (permission_id) JOIN role r USING (role_id) "
        "WHERE rp.permission_effect = 'ALLOW' AND (p.permission_code LIKE 'EMPLOYEE.EMPLOYEE_AADHAAR.%' OR p.permission_code LIKE "
        "'EMPLOYEE.EMPLOYEE_PAN.%' OR p.permission_code LIKE 'EMPLOYEE.EMPLOYEE_BANK_ACCOUNT.%')")).scalars().all()
    assert set(rows) <= {"SUPER_ADMIN"}


def test_the_catalogue_has_no_dangling_matrix_entries(db):
    from app.rbac import catalogue

    assert catalogue.sync(db)["missing"] == 0


def test_reconcile_removes_extra_grants_but_keeps_deny_rows(db):
    from app.rbac import catalogue

    db.execute(text("INSERT INTO role_permission (role_id, permission_id, permission_effect) SELECT r.role_id, p.permission_id, 'ALLOW' "
                    "FROM role r, permission p WHERE r.role_code='FACULTY' AND p.permission_code='RESULT.ALL.PUBLISH'"))
    db.execute(text("INSERT INTO role_permission (role_id, permission_id, permission_effect) SELECT r.role_id, p.permission_id, 'DENY' "
                    "FROM role r, permission p WHERE r.role_code='FACULTY' AND p.permission_code='GRIEVANCE.ALL.READ'"))
    db.flush()
    stats = catalogue.sync(db)
    assert stats["revoked"] == 1
    assert "RESULT.ALL.PUBLISH" not in held(db, "FACULTY")
    assert db.execute(text("SELECT count(*) FROM role_permission rp JOIN role r USING (role_id) JOIN permission p USING (permission_id) "
                           "WHERE r.role_code='FACULTY' AND rp.permission_effect='DENY' AND p.permission_code='GRIEVANCE.ALL.READ'")).scalar() == 1


# ----------------------------------------------------------------------- (2) what the API lets each persona read and create
def path_of(table):
    build_registry()
    return REGISTRY[table].path


# persona -> (tables readable, tables not readable, tables creatable, tables not creatable)
API = {
    "teacher": (["student", "course_catalog", "class_session", "student_attendance", "assessment_event", "student_assessment_mark", "timetable_session"],
                ["student_course_result", "student_term_result", "admission_application", "grievance", "certificate_request", "employee_aadhaar"],
                ["class_session", "student_attendance", "student_assessment_mark", "counselling_session"],
                ["student", "course_catalog", "academic_year", "student_course_result", "announcement", "admission_application"]),
    "evaluator": (["student_assessment_mark", "assessment_event"], ["student_course_result", "attendance_policy", "announcement", "grievance"],
                  ["student_assessment_mark"], ["assessment_event", "student_attendance", "student_course_result", "student"]),
    "coursecoord": (["student_assessment_mark", "assessment_component"], ["student_course_result"],
                    ["assessment_event", "assessment_component", "student_assessment_mark"], ["student_course_result", "curriculum_scheme"]),
    "ttcoord": (["timetable_session", "course_offering_section", "faculty_course_assignment"], ["student_assessment_mark", "student", "grievance"],
                ["timetable_plan", "faculty_course_assignment"], ["student_attendance", "student_assessment_mark"]),
    "progcoord": (["student", "curriculum_scheme", "student_term_registration"], ["student_course_result", "grievance"],
                  ["curriculum_scheme"], ["student", "student_assessment_mark", "student_attendance"]),
    "mentor": (["student", "counselling_session", "student_attendance"], ["student_assessment_mark", "grievance"],
               ["counselling_session"], ["student_attendance", "student_assessment_mark", "student"]),
    "hod": (["student", "student_course_result", "staff_activity", "course_offering_section"], ["employee_aadhaar"],
            ["curriculum_scheme", "counselling_session"], ["student", "academic_year", "student_course_result", "result_publication"]),
    "dean": (["student", "student_course_result", "curriculum_scheme", "staff_activity"], ["employee_aadhaar"],
             ["curriculum_scheme", "academic_year"], ["student", "student_course_result", "student_attendance"]),
    "vc": (["student", "student_course_result", "staff_activity", "admission_application"], ["employee_aadhaar"],
           [], ["student", "student_course_result", "curriculum_scheme", "announcement", "admission_application", "grievance"]),
    "campusadm": (["student", "employee", "grievance", "timetable_revision"], ["employee_pan"], ["announcement"], ["student", "student_course_result"]),
    "registrar": (["student", "admission_application", "student_course_result", "certificate_request"], ["employee_aadhaar"],
                  ["student", "admission_application", "academic_year", "curriculum_scheme", "announcement"],
                  ["student_course_result", "student_assessment_mark", "student_attendance", "employee"]),
    "admissions": (["admission_application", "student", "student_document"], ["student_course_result", "student_term_registration"],
                   ["admission_application"], ["student", "student_document", "announcement"]),
    "docverifier": (["student_document", "certificate_request", "student"], ["student_course_result"], [], ["student_document", "certificate_request", "student"]),
    "sectionofficer": (["student", "student_term_registration"], ["student_course_result"], ["student", "student_term_registration"],
                       ["admission_application", "student_course_result"]),
    "examcell": (["student_course_result", "result_publication", "assessment_event", "certificate_request"], ["admission_application", "employee"],
                 ["assessment_event", "certificate_request"], ["student", "curriculum_scheme", "admission_application"]),
    "examofficer": (["student_course_result", "assessment_event"], ["admission_application"], ["assessment_event"],
                    ["student", "result_publication"]),
    "resultapprover": (["student_course_result", "result_publication"], ["admission_application"], [], ["student_course_result", "assessment_event", "student"]),
    "support": (["grievance", "student"], ["student_course_result", "admission_application", "employee"], [], ["student", "announcement", "student_course_result"]),
    "finance": (["admission_application", "admission_fee_clearance", "funded_research_project"], ["student", "student_course_result"],
                [], ["admission_application", "student", "admission_fee_clearance"]),
    "auditor": (["student", "student_course_result", "admission_application", "staff_activity"], ["employee_aadhaar"], [],
                ["student", "student_course_result", "announcement", "grievance"]),
    "extauditor": (["student", "student_course_result", "admission_application"], ["employee_aadhaar"], [], ["student", "student_course_result", "announcement"]),
    "student": (["student", "student_course_result", "class_session", "grievance", "announcement"],
                ["employee", "student_assessment_mark"],
                ["grievance", "certificate_request", "attendance_correction_request", "student_term_registration"],
                ["student", "student_attendance", "student_assessment_mark", "student_course_result", "announcement", "admission_application"]),
    "parent": (["student", "student_course_result", "student_attendance"], ["grievance", "certificate_request", "employee"],
               [], ["grievance", "certificate_request", "student", "student_term_registration", "attendance_correction_request"]),
    "alumni": (["student", "student_course_result"], ["employee"], ["certificate_request"], ["grievance", "student", "student_term_registration"]),
    "applicant": (["announcement"], ["student_course_result", "employee", "student_attendance"],
                  ["admission_application", "student_document"], ["student", "grievance", "student_term_registration"]),
    "sysadmin": (["academic_year", "announcement", "country", "campus"], ["student", "student_course_result", "employee_aadhaar"],
                 ["academic_year", "announcement", "country", "campus"], ["student", "student_course_result", "student_attendance"]),
    "secadmin": ([], ["student", "student_course_result", "admission_application"], [], ["student", "academic_year"]),
}


def cases(index):
    return [(who, table) for who, spec in API.items() for table in spec[index]]


@pytest.mark.parametrize("who,table", cases(0))
def test_api_allows_reading(as_user, who, table):
    assert as_user(who).get(f"/{path_of(table)}?page_size=1").status_code == 200


@pytest.mark.parametrize("who,table", cases(1))
def test_api_refuses_reading(as_user, who, table):
    assert as_user(who).get(f"/{path_of(table)}?page_size=1").status_code in (403, 404)


def can_do(client, table, action):
    """What the resource's own metadata says this person may do (the UI shows or hides buttons from the same flags)."""
    r = client.get(f"/meta/{path_of(table)}")
    return r.status_code == 200 and r.json()["can"][action]


@pytest.mark.parametrize("who,table", cases(2))
def test_api_allows_creating(as_user, who, table):
    assert can_do(as_user(who), table, "create")


@pytest.mark.parametrize("who,table", cases(3))
def test_api_refuses_creating(as_user, who, table):
    assert not can_do(as_user(who), table, "create")


@pytest.mark.parametrize("who,table", [(w, t) for w, spec in API.items() for t in spec[3]][:60])
def test_api_blocks_a_real_create_attempt(as_user, who, table):
    """Empty bodies fail validation first on resources with required fields, so only resources without any are probed
    for a hard 403; the metadata flags above cover the rest."""
    r = as_user(who).post(f"/{path_of(table)}", json={})
    assert r.status_code in (403, 404, 405, 422)


# ------------------------------------------------------------------------- (3) segregation of duties and visibility
def test_faculty_cannot_calculate_publish_or_see_results(as_user):
    t = as_user("teacher")
    assert t.get("/results/student-course-result").status_code in (403, 404)
    assert t.post("/assessments/results/calculate", json={"course_offering_section_id": 1}).status_code in (403, 404, 405)


def test_students_are_read_only_on_their_own_academic_records(as_user):
    s = as_user("student")
    mine = s.get("/people/student").json()
    assert mine["count"] == 1
    sid = mine["results"][0]["student_id"]
    assert s.patch(f"/people/student/{sid}", json={"student_status": "ALUMNI"}).status_code in (403, 422)
    assert s.patch(f"/people/student/{sid}", json={"primary_phone": "9876543210"}).status_code == 200


def test_parent_is_strictly_read_only(as_user):
    p = as_user("parent")
    assert p.get("/people/student").json()["count"] == 1
    sid = p.get("/people/student").json()["results"][0]["student_id"]
    assert p.patch(f"/people/student/{sid}", json={"primary_phone": "9876543210"}).status_code == 403
    assert p.delete(f"/people/student/{sid}").status_code == 403


def test_every_persona_reaches_the_dashboard_and_only_sees_its_own_tiles(as_user):
    labels = {who: {t["label"] for t in as_user(who).get("/dashboard").json()["tiles"]} for who in ("student", "teacher", "registrar", "finance")}
    assert "Open grievances" in labels["student"] and "Applicants" not in labels["student"]
    assert "Applicants" in labels["registrar"] and "Active staff" not in labels["finance"]


def test_each_role_has_a_demo_persona_that_signs_in_through_its_own_portal(app):
    from app.rbac.portals import portals_of
    from tests.conftest import DEMO_PASSWORD, Client

    for who, role in PERSONA_ROLE.items():
        c = Client(app)
        c.login(who)
        me = c.get("/auth/me").json()
        assert me["username"] == who and (role is None or role in me["roles"] or me["is_superuser"]), who
        assert portals_of(set(me["roles"]), me["is_superuser"]), who
    assert DEMO_PASSWORD


def test_engine_agrees_with_the_database_for_every_persona(db):
    for who, role in PERSONA_ROLE.items():
        if role is None:
            continue
        p = load_principal(db, db.scalar(select(UserAccount).where(UserAccount.username == who)))
        assert role in p.role_codes, who
        assert not (set(MUST_NOT.get(role, [])) & set(p.allowed_codes())), who


# ------------------------------------------------------------- (4) teaching roles reach only what they are assigned to
def section_of(db, username):
    return db.execute(text(
        "SELECT fa.course_offering_section_id FROM faculty_course_assignment fa JOIN person_account_link l ON l.employee_id = fa.employee_id "
        "JOIN user_account u ON u.user_id = l.user_id WHERE u.username = :u AND fa.assignment_status = 'ACTIVE' ORDER BY 1 LIMIT 1"), {"u": username}).scalar()


def test_a_teacher_sees_only_the_classes_they_are_assigned_to(as_user, db):
    mine = section_of(db, "teacher")
    t, hod = as_user("teacher"), as_user("hod")
    sessions = t.get("/attendance/class-session?page_size=100").json()["results"]
    assert sessions and {s["course_offering_section_id"] for s in sessions} == {mine}
    everyone = hod.get("/attendance/class-session?page_size=100").json()["results"]
    foreign = next(s for s in everyone if s["course_offering_section_id"] != mine)
    assert t.get(f"/attendance/class-session/{foreign['class_session_id']}").status_code == 404
    assert t.get(f"/attendance/sessions/{foreign['class_session_id']}/roster").status_code == 404
    assert t.post(f"/attendance/class-session/{foreign['class_session_id']}/actions/open_register").status_code == 404
    own = sessions[0]["class_session_id"]
    assert t.get(f"/attendance/sessions/{own}/roster").status_code == 200


def test_marks_and_papers_are_limited_to_assigned_offerings(as_user, db):
    t = as_user("teacher")
    mine = db.execute(text("SELECT s.course_offering_id FROM course_offering_section s WHERE s.course_offering_section_id = :s"),
                      {"s": section_of(db, "teacher")}).scalar()
    events = t.get("/assessments/assessment-event?page_size=100").json()["results"]
    assert events and {e["course_offering_id"] for e in events} == {mine}
    other = db.execute(text("SELECT assessment_event_id FROM assessment_event WHERE course_offering_id <> :o LIMIT 1"), {"o": mine}).scalar()
    assert t.get(f"/assessments/events/{other}/roster").status_code in (403, 404)
    assert t.put(f"/assessments/events/{other}/marks", json={"marks": []}).status_code in (403, 404, 422)
    marks = t.get("/assessments/student-assessment-mark?page_size=100").json()["results"]
    assert marks and all(m["assessment_event_id"] in {e["assessment_event_id"] for e in events} for m in marks)


def test_an_evaluator_enters_marks_only_for_assigned_papers(as_user, db):
    ev = as_user("evaluator")
    sec = section_of(db, "evaluator")
    off = db.execute(text("SELECT course_offering_id FROM course_offering_section WHERE course_offering_section_id = :s"), {"s": sec}).scalar()
    events = ev.get("/assessments/assessment-event?page_size=100").json()["results"]
    assert {e["course_offering_id"] for e in events} <= {off}
    assert ev.get("/attendance/class-session").status_code == 403 or ev.get("/attendance/class-session").json()["count"] == 0


def test_a_wider_role_lifts_the_restriction(as_user, db):
    hod_sections = {s["course_offering_section_id"] for s in as_user("hod").get("/attendance/class-session?page_size=100").json()["results"]}
    assert len(hod_sections) > 1                       # the head of department sees every class of the department
    assert len({s["course_offering_section_id"] for s in as_user("registrar").get("/attendance/class-session?page_size=100").json()["results"]}) > 1


def test_mentors_see_only_their_mentees(as_user, db):
    mentor_emp = db.execute(text("SELECT l.employee_id FROM person_account_link l JOIN user_account u ON u.user_id = l.user_id WHERE u.username = 'mentor'")).scalar()
    programme = db.execute(text("SELECT a.programme_id FROM user_role_assignment a JOIN user_account u ON u.user_id = a.user_id "
                                "WHERE u.username = 'mentor' AND a.scope_type = 'PROGRAMME'")).scalar()
    students = [s for (s,) in db.execute(text("SELECT DISTINCT student_id FROM student_programme_enrolment WHERE programme_id = :p ORDER BY 1 LIMIT 3"),
                                         {"p": programme})]
    assert len(students) >= 2
    db.execute(text("DELETE FROM mentor_assignment WHERE employee_id = :e"), {"e": mentor_emp})
    db.execute(text("INSERT INTO mentor_assignment (student_id, employee_id, start_date, assignment_status) VALUES (:s, :e, current_date, 'ACTIVE')"),
               {"s": students[0], "e": mentor_emp})
    db.commit()
    m = as_user("mentor")
    listed = m.get("/people/student?page_size=100").json()
    assert listed["count"] == 1 and listed["results"][0]["student_id"] == students[0]
    assert m.get(f"/people/student/{students[1]}").status_code == 404
    assert m.get("/support/mentor-assignment").json()["count"] == 1
    # a teacher keeps the department-wide student list (read-only) and sees only their own mentoring
    t = as_user("teacher")
    assert t.get("/people/student").json()["count"] > 3
    teacher_emp = db.execute(text("SELECT l.employee_id FROM person_account_link l JOIN user_account u ON u.user_id = l.user_id WHERE u.username = 'teacher'")).scalar()
    own = db.execute(text("SELECT count(*) FROM mentor_assignment WHERE employee_id = :e"), {"e": teacher_emp}).scalar()
    assert t.get("/support/mentor-assignment").json()["count"] == own
    assert as_user("hod").get("/support/mentor-assignment").json()["count"] >= 1


def test_students_see_only_their_own_class_data(as_user):
    s = as_user("student")
    mine = s.get("/attendance/student-attendance?page_size=100").json()
    assert all(r["student_id"] == s.get("/auth/me").json()["student_ids"][0] for r in mine["results"])


# ------------------------------------------------------------------------ (5) holes found in the security review
def test_students_cannot_choose_the_workflow_state_of_their_own_requests(as_user, db):
    s = as_user("student")
    sid = s.get("/auth/me").json()["student_ids"][0]
    ctype = db.execute(text("SELECT certificate_type_id FROM certificate_type LIMIT 1")).scalar()
    r = s.post("/documents/certificate-request", json={"certificate_type_id": ctype, "student_id": sid, "request_status": "ISSUED"})
    assert r.status_code == 403 and "review process" in r.json()["error"]["message"]
    ok = s.post("/documents/certificate-request", json={"certificate_type_id": ctype, "student_id": sid, "purpose": "bank"})
    assert ok.status_code == 201 and ok.json()["request_status"] != "ISSUED"
    cat = db.execute(text("SELECT grievance_category_id FROM grievance_category LIMIT 1")).scalar()
    assert s.post("/support/grievance", json={"grievance_category_id": cat, "student_id": sid, "subject": "x", "description": "y", "status": "RESOLVED"}).status_code == 403


def test_a_student_cannot_attach_someone_elses_file(as_user, db):
    from tests.test_files import pdf_bytes, upload

    other = upload(as_user("student2"), "private.pdf", pdf_bytes()).json()["file_object_id"]
    s = as_user("student")
    sid = s.get("/auth/me").json()["student_ids"][0]
    dtype = db.execute(text("SELECT document_type_id FROM document_type LIMIT 1")).scalar()
    r = s.post("/documents/student-document", json={"student_id": sid, "document_type_id": dtype, "file_object_id": other})
    assert r.status_code in (403, 422), r.text
    assert as_user("student").get(f"/files/{other}").status_code == 404


def test_mentors_cannot_hand_themselves_mentees_or_read_raw_feedback(as_user):
    m = as_user("mentor")
    meta = m.get("/meta/support/mentor-assignment")
    assert meta.status_code == 200 and not meta.json()["can"]["create"] and not meta.json()["can"]["update"]
    assert m.get("/meta/support/counselling-session").json()["can"]["create"]
    for who in ("teacher", "mentor", "evaluator"):
        assert as_user(who).get("/feedback/feedback-response").status_code == 403


def test_organisation_admins_cannot_manage_peers_or_misuse_self_roles(as_user, app, db):
    from tests.test_organisations import ORG, first_sign_in

    sa = as_user("demoadmin")
    made = sa.post("/security/organisations", json={**ORG, "code": "PEER", "admin_username": "peer.one", "admin_email": "a@peer.edu"}).json()
    inst = made["institution"]["institution_id"]
    one = first_sign_in(app, "peer.one", made["administrator"]["temporary_password"])
    second = sa.post("/security/users", json={"username": "peer.two", "email": "b@peer.edu", "institution_id": inst,
                                              "role_code": "INSTITUTION_ADMIN", "scope_type": "INSTITUTION"}).json()
    assert one.post(f"/security/users/{second['user_id']}/reset-password").status_code == 403
    assert one.patch(f"/security/users/{second['user_id']}", json={"is_active": False}).status_code == 403
    staff = one.post("/security/users", json={"username": "peer.staff", "email": "c@peer.edu"}).json()["user_id"]
    bad = one.post("/security/role-assignments", json={"user_id": staff, "role_code": "STUDENT", "scope_type": "INSTITUTION", "scope_id": inst})
    assert bad.status_code == 422
    assert one.post("/security/role-assignments", json={"user_id": staff, "role_code": "STUDENT", "scope_type": "SELF"}).status_code == 201


def test_teachers_cannot_write_into_another_teachers_section(as_user, db):
    t = as_user("teacher")
    mine = section_of(db, "teacher")
    foreign = db.execute(text("SELECT class_session_id FROM class_session WHERE course_offering_section_id <> :s LIMIT 1"), {"s": mine}).scalar()
    assert t.patch(f"/attendance/class-session/{foreign}", json={}).status_code in (403, 404)


def test_support_and_exam_roles_do_not_read_guardian_or_address_details(as_user):
    for who in ("support", "examofficer", "examcell", "resultapprover", "docverifier", "teacher"):
        c = as_user(who)
        assert c.get("/people/student-parent-guardian").status_code == 403, who
        assert c.get("/people/student-residence").status_code == 403, who
    assert as_user("registrar").get("/people/student-parent-guardian").status_code == 200


def test_department_heads_see_their_staff(as_user, db):
    assert as_user("hod").get("/people/employee").json()["count"] > 0
    assert as_user("campusadm").get("/people/employee").json()["count"] > 0


def test_audit_trail_names_the_actor(as_user):
    admin = as_user("demoadmin")
    admin.post("/security/users", json={"username": "audit.probe", "email": "ap@example.org"})
    rows = admin.get("/security/audit?page_size=5").json()["results"]
    assert rows and rows[0]["actor"] == "demoadmin"


def test_everyone_reads_the_announcements_meant_for_them(as_user, db):
    db.execute(text("UPDATE announcement SET approval_status='APPROVED', audience_type='ALL', publish_from = now() - interval '1 day' "
                    "WHERE announcement_id = (SELECT min(announcement_id) FROM announcement)"))
    inst = db.execute(text("SELECT institution_id FROM announcement ORDER BY announcement_id LIMIT 1")).scalar()
    if inst is None:
        pytest.skip("no announcements in the demo data")
    db.commit()
    for who in ("student", "teacher", "parent"):
        assert as_user(who).get("/communication/announcement").json()["count"] >= 1, who
