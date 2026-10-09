"""Demo content for the non-academic services: idempotent seeding, and every persona finds real rows in its own lists."""
import pytest
from sqlalchemy import text

from app.seed.content_services import ensure_service_content

TABLES = [
    "announcement", "notification", "grievance_category", "grievance", "grievance_action", "certificate_request", "document_type",
    "file_object", "student_document", "admission_applicant", "admission_application", "admission_fee_clearance",
    "student_parent_guardian", "student_address", "student_residence", "student_previous_education", "registration_policy",
    "student_term_result", "student_course_result", "feedback_questionnaire", "feedback_questionnaire_item", "feedback_question",
    "feedback_choice", "feedback_cycle", "feedback_response", "feedback_response_item", "feedback_response_item_choice",
    "staff_activity", "journal_publication", "staff_award", "conference_activity", "funded_research_project", "consultancy_project",
    "research_proposal", "staff_professional_membership", "evidence_document", "employee_qualification", "employee_address",
]


def counts(db):
    return {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in TABLES}  # noqa: S608


@pytest.fixture()
def seeded(db):
    ensure_service_content(db)
    return db


def rows(client, path, **params):
    r = client.get(path, params={"page_size": 100, **params})
    assert r.status_code == 200, (path, r.text)
    return r.json()["results"]


def student_id(db, username):
    return db.execute(text("SELECT l.student_id FROM person_account_link l JOIN user_account u USING (user_id) WHERE u.username = :u"),
                      {"u": username}).scalar()


def test_seeding_is_idempotent(db):
    ensure_service_content(db)
    before = counts(db)
    again = ensure_service_content(db)
    assert again == {}
    assert counts(db) == before


def test_seeding_reports_only_what_it_inserted(db):
    # rows added by one call equal the growth of the tables, so the report can be trusted by the demo loader
    before = counts(db)
    added = ensure_service_content(db)
    after = counts(db)
    for table, n in added.items():
        if table in before:
            assert after[table] - before[table] == n, table


def test_students_see_their_own_service_records(seeded, as_user):
    for persona in ("student", "student2"):
        c = as_user(persona)
        sid = student_id(seeded, persona)
        grievances = rows(c, "/support/grievance")
        assert {g["status"] for g in grievances} >= {"SUBMITTED", "UNDER_REVIEW", "RESOLVED"}
        assert {g["student_id"] for g in grievances} == {sid}
        certificates = rows(c, "/documents/certificate-request")
        assert {r["request_status"] for r in certificates} >= {"SUBMITTED", "UNDER_REVIEW", "APPROVED", "ISSUED", "REJECTED"}
        assert {r["student_id"] for r in certificates} == {sid}
        documents = rows(c, "/documents/student-document")
        assert {d["verification_status"] for d in documents} >= {"PENDING", "VERIFIED"}
        notifications = c.get("/notifications").json()
        assert notifications["count"] >= 2
        # family and background records were filled in too
        assert rows(c, "/people/student-parent-guardian") and rows(c, "/people/student-residence")
        assert rows(c, "/people/student-previous-education") and rows(c, "/people/student-address")
    student = as_user("student")
    states = {r["status"] for r in rows(student, "/support/grievance")}
    assert len(states) >= 3
    # open feedback cycle: the student has courses waiting to be reviewed
    assert student.get("/feedback/pending").json()["results"]


def test_announcements_cover_states_audiences_and_dates(seeded, as_user):
    registrar = as_user("registrar")
    items = rows(registrar, "/communication/announcement")
    assert {"APPROVED", "PENDING", "DRAFT"} <= {a["approval_status"] for a in items}
    assert {"STUDENTS", "STAFF", "ALL"} <= {a["audience_type"] for a in items}
    assert seeded.execute(text("SELECT count(*) FROM announcement WHERE approval_status = 'APPROVED'")).scalar() >= 3
    assert seeded.execute(text("SELECT count(*) FROM announcement WHERE approval_status = 'APPROVED' AND publish_from > now()")).scalar() == 0
    assert seeded.execute(text("SELECT count(*) FROM announcement WHERE institution_id IS NULL")).scalar() == 0
    # staff scoped to the department see the department notices; every demo login has notifications waiting
    assert rows(as_user("hod"), "/communication/announcement")
    unread = seeded.execute(text(
        "SELECT count(DISTINCT n.user_id) FROM notification n JOIN user_account u USING (user_id) WHERE u.username IN "
        "('student', 'student2', 'parent', 'alumni', 'applicant', 'registrar', 'hod', 'teacher', 'support', 'finance')")).scalar()
    assert unread == 10


def test_back_office_queues_are_not_empty(seeded, as_user):
    registrar = as_user("registrar")
    applications = rows(registrar, "/admissions/admission-application")
    assert {"SUBMITTED", "UNDER_REVIEW", "ELIGIBLE", "SELECTED", "REJECTED"} <= {a["application_status"] for a in applications}
    certificates = rows(registrar, "/documents/certificate-request")
    assert {"SUBMITTED", "UNDER_REVIEW", "APPROVED", "ISSUED", "REJECTED"} <= {r["request_status"] for r in certificates}

    # fee clearances: some selected applications are cleared, others are still waiting for finance
    assert len(rows(as_user("finance"), "/admissions/admission-fee-clearance")) >= 3
    assert seeded.execute(text(
        "SELECT count(*) FROM admission_application a WHERE a.application_status = 'SELECTED' AND NOT EXISTS "
        "(SELECT 1 FROM admission_fee_clearance f WHERE f.application_id = a.application_id)")).scalar() >= 1

    documents = rows(as_user("docverifier"), "/documents/student-document")
    assert {"PENDING", "VERIFIED", "REJECTED"} <= {d["verification_status"] for d in documents}

    grievances = rows(as_user("support"), "/support/grievance")
    assert {"SUBMITTED", "ASSIGNED", "UNDER_REVIEW", "RESOLVED"} <= {g["status"] for g in grievances}
    assert len({g["student_id"] for g in grievances}) >= 5
    assert seeded.execute(text("SELECT count(*) FROM grievance g WHERE NOT EXISTS (SELECT 1 FROM grievance_action a "
                               "WHERE a.grievance_id = g.grievance_id)")).scalar() == 0


def test_review_chains_for_staff_records_have_items(seeded, as_user):
    for persona in ("hod", "dean", "vc"):
        items = rows(as_user(persona), "/staff-activities/staff-activity")
        statuses = {i["approval_status_id"] for i in items}
        assert len(items) >= 20 and len(statuses) >= 5, persona
    states = {s for (s,) in seeded.execute(text(
        "SELECT a.status_code FROM staff_activity sa JOIN approval_status a USING (approval_status_id)"))}
    assert {"DRAFT", "SUBMITTED", "UNDER_REVIEW", "RETURNED", "VERIFIED", "APPROVED", "REJECTED"} <= states
    # the record types that need their own detail row all got some
    for table in ("journal_publication", "staff_award", "conference_activity", "funded_research_project", "consultancy_project",
                  "research_proposal", "staff_professional_membership", "evidence_document"):
        assert seeded.execute(text(f"SELECT count(*) FROM {table}")).scalar() > 0, table  # noqa: S608
    # staff personas own records, and their HR profile pages have qualifications and addresses
    for persona in ("teacher", "hod"):
        assert rows(as_user(persona), "/staff-activities/staff-activity")
    assert seeded.execute(text(
        "SELECT count(*) FROM employee e WHERE NOT EXISTS (SELECT 1 FROM employee_qualification q WHERE q.employee_id = e.employee_id)")).scalar() == 0
    assert seeded.execute(text(
        "SELECT count(*) FROM employee e WHERE NOT EXISTS (SELECT 1 FROM employee_address a WHERE a.employee_id = e.employee_id)")).scalar() == 0


def test_alumni_has_a_published_result_and_an_issued_certificate(seeded, as_user):
    sid = student_id(seeded, "alumni")
    assert seeded.execute(text("SELECT student_status FROM student WHERE student_id = :s"), {"s": sid}).scalar() in ("ALUMNUS", "COMPLETED")
    alumni = as_user("alumni")
    requests = rows(alumni, "/documents/certificate-request")
    assert requests and {r["student_id"] for r in requests} == {sid}
    assert "ISSUED" in {r["request_status"] for r in requests}
    assert all(r["certificate_number"] for r in requests if r["request_status"] == "ISSUED")
    term = rows(alumni, "/assessments/student-term-result")
    assert term and {t["state"] for t in term} == {"PUBLISHED"}
    course = rows(alumni, "/assessments/student-course-result")
    assert course and {t["state"] for t in course} == {"PUBLISHED"}


def test_applicant_is_mid_pipeline_with_documents(seeded, as_user):
    sid = student_id(seeded, "applicant")
    assert seeded.execute(text("SELECT student_status FROM student WHERE student_id = :s"), {"s": sid}).scalar() == "APPLICANT"
    applicant = as_user("applicant")
    applications = rows(applicant, "/admissions/admission-application")
    assert {"UNDER_REVIEW", "SUBMITTED"} & {a["application_status"] for a in applications}
    documents = rows(applicant, "/documents/student-document")
    assert {d["verification_status"] for d in documents} >= {"PENDING", "VERIFIED"}


def test_feedback_has_an_open_and_a_closed_cycle_with_responses(seeded):
    statuses = {s for (s,) in seeded.execute(text("SELECT status FROM feedback_cycle"))}
    assert {"OPEN", "CLOSED"} <= statuses
    closed = seeded.execute(text("SELECT fc.feedback_cycle_id FROM feedback_cycle fc WHERE fc.status = 'CLOSED' AND "
                                 "fc.minimum_cohort <= (SELECT count(*) FROM feedback_response r "
                                 "WHERE r.feedback_cycle_id = fc.feedback_cycle_id) LIMIT 1")).scalar()
    assert closed is not None
    questionnaire = seeded.execute(text("SELECT questionnaire_id FROM feedback_questionnaire WHERE questionnaire_code = 'DEMO-COURSE-FB'")).scalar()
    assert seeded.execute(text("SELECT count(*) FROM feedback_questionnaire_item WHERE questionnaire_id = :q"), {"q": questionnaire}).scalar() >= 5
    assert seeded.execute(text("SELECT count(*) FROM feedback_choice")).scalar() >= 3
    assert seeded.execute(text("SELECT count(*) FROM registration_policy")).scalar() >= 1
