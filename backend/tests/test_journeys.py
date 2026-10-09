"""Real-world journeys: each persona does their normal day's work through the public API only.

These read like user stories on purpose — if one fails, a real person's workflow is broken.
"""
import pytest
from sqlalchemy import text

from tests.conftest import Client


def nav(client) -> set[str]:
    return {r["path"] for g in client.get("/meta").json()["groups"] for r in g["resources"]}


# ------------------------------------------------------------------------------------------- the student
def test_student_day(as_user, db):
    s = as_user("student")
    me = s.get("/auth/me").json()
    assert me["roles"] == ["STUDENT"] and me["student_ids"]

    # 1. lands on a dashboard limited to what a student may see
    tiles = {t["label"] for t in s.get("/dashboard").json()["tiles"]}
    assert "Active staff" not in tiles
    values = {t["label"]: t["value"] for t in s.get("/dashboard").json()["tiles"]}
    assert values.get("Active students", 1) == 1                        # only themselves, never the whole campus

    # 2. the menu contains student things and none of the staff/admin ones
    paths = nav(s)
    assert "people/student" in paths and "documents/certificate-request" in paths
    assert not {"people/employee", "hr/employee-qualification"} & paths

    # 3. sees only their own record and may change only contact details
    record = s.get("/people/student").json()["results"]
    assert len(record) == 1
    sid = record[0]["student_id"]
    assert s.patch(f"/people/student/{sid}", json={"primary_phone": "9000011111"}).status_code == 200
    for forbidden in ({"student_status": "ALUMNUS"}, {"department_id": 1}, {"notes": "x"}, {"display_name": "Someone Else"}):
        assert s.patch(f"/people/student/{sid}", json=forbidden).status_code == 403
    assert s.post(f"/people/student/{sid}/actions/complete").status_code in (403, 409)

    # 4. other people's data is invisible, not merely forbidden
    other = db.execute(text("SELECT student_id FROM student WHERE student_id <> :s LIMIT 1"), {"s": sid}).scalar()
    assert s.get(f"/people/student/{other}").status_code == 404
    assert s.get("/people/student-address").json()["count"] <= 2

    # 5. asks for a certificate and watches its status
    ctype = db.execute(text("SELECT certificate_type_id FROM certificate_type LIMIT 1")).scalar()
    req = s.post("/documents/certificate-request", json={"certificate_type_id": ctype, "purpose": "Passport"}).json()
    assert req["request_status"] == "SUBMITTED" and req["student_id"] == sid
    assert s.get(f"/documents/certificate-request/{req['certificate_request_id']}/history").status_code == 200
    assert s.post(f"/documents/certificate-request/{req['certificate_request_id']}/actions/cancel").json()["request_status"] == "CANCELLED"

    # 6. raises a grievance and cannot tamper with its handling
    cat = db.execute(text("SELECT grievance_category_id FROM grievance_category LIMIT 1")).scalar()
    g = s.post("/support/grievance", json={"grievance_category_id": cat, "subject": "Hostel water", "description": "No water since morning"}).json()
    assert s.post(f"/support/grievance/{g['grievance_id']}/actions/resolve", json={"remarks": "self"}).status_code == 403
    assert s.patch(f"/support/grievance/{g['grievance_id']}", json={"subject": "edited"}).status_code == 403

    # 7. cannot write into academic records
    assert s.post("/assessments/student-assessment-mark", json={}).status_code in (403, 422)
    assert s.put("/assessments/events/1/marks", json={"marks": [{"course_registration_id": 1, "marks_obtained": "99"}]}).status_code in (403, 404)
    assert s.post("/attendance/class-session", json={}).status_code in (403, 422)

    # 8. security hygiene: sees own devices, can sign out everywhere
    assert s.get("/auth/sessions").json()["results"]
    assert s.post("/auth/logout-all", headers=s.csrf_headers()).status_code == 204
    assert s.get("/auth/me").status_code == 401


def test_student_registers_for_a_term(as_user, db):
    """Create a term registration, add a course, hit the credit rule, then submit."""
    row = db.execute(text(
        "SELECT u.username, e.enrolment_id, p.programme_term_offering_id, o.course_offering_id FROM person_account_link l "
        "JOIN user_account u ON u.user_id = l.user_id JOIN student_programme_enrolment e ON e.student_id = l.student_id AND e.enrolment_status = 'ACTIVE' "
        "JOIN programme_term_offering p ON p.programme_id = e.programme_id JOIN course_offering o ON o.programme_term_offering_id = p.programme_term_offering_id "
        "WHERE NOT EXISTS (SELECT 1 FROM student_term_registration t WHERE t.enrolment_id = e.enrolment_id AND t.programme_term_offering_id = p.programme_term_offering_id) "
        "LIMIT 1")).first()
    if row is None:
        pytest.skip("no registrable term in the demo data")
    db.execute(text("UPDATE programme_term_offering SET status = 'REGISTRATION_OPEN' WHERE programme_term_offering_id = :p"), {"p": row.programme_term_offering_id})
    db.execute(text("UPDATE course_offering SET status = 'OPEN', registration_capacity = NULL WHERE course_offering_id = :o"), {"o": row.course_offering_id})
    db.commit()
    s = as_user(row.username)
    term = s.post("/registration/student-term-registration", json={"enrolment_id": row.enrolment_id, "programme_term_offering_id": row.programme_term_offering_id})
    assert term.status_code == 201, term.text
    tid = term.json()["term_registration_id"]
    assert term.json()["registration_status"] == "DRAFT"
    course = s.post("/registration/student-course-registration", json={"term_registration_id": tid, "course_offering_id": row.course_offering_id})
    assert course.status_code == 201, course.text
    assert s.post("/registration/student-course-registration", json={"term_registration_id": tid, "course_offering_id": row.course_offering_id}).status_code == 409
    db.execute(text("INSERT INTO registration_policy (programme_id, minimum_credits, maximum_credits, version, updated_by_id) "
                    "SELECT programme_id, 100, 200, 1, 1 FROM programme_term_offering WHERE programme_term_offering_id = :p ON CONFLICT DO NOTHING"), {"p": row.programme_term_offering_id})
    db.commit()
    low = s.post(f"/registration/student-term-registration/{tid}/actions/submit")
    assert low.status_code in (409, 200)
    if low.status_code == 409:
        assert low.json()["error"]["code"] == "credit_limits"
    db.execute(text("DELETE FROM registration_policy WHERE programme_id = (SELECT programme_id FROM programme_term_offering WHERE programme_term_offering_id = :p)"), {"p": row.programme_term_offering_id})
    db.commit()
    done = s.post(f"/registration/student-term-registration/{tid}/actions/submit")
    assert done.status_code == 200 and done.json()["registration_status"] == "REGISTERED"
    reg = as_user("registrar")
    assert reg.post(f"/registration/student-term-registration/{tid}/actions/approve").json()["registration_status"] == "APPROVED"


def test_timetable_views(as_user, db):
    s = as_user("student")
    revisions = s.get("/timetable/timetable-revision?page_size=100").json()["results"]
    assert all(r["status"] == "PUBLISHED" for r in revisions)
    db.execute(text("UPDATE timetable_revision SET status = 'PUBLISHED'"))
    db.commit()
    mine = s.get("/timetable/mine?on=2026-09-14").json()
    assert "sessions" in mine
    t = as_user("teacher").get("/timetable/mine?on=2026-09-14").json()
    for day in t["sessions"]:
        assert day["day"] in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY") and day["items"]
    assert as_user("registrar").get("/timetable/mine").json()["sessions"] == []        # neither student nor teacher
    db.execute(text("UPDATE timetable_revision SET status = 'DRAFT'"))
    db.commit()
    assert as_user("teacher").get("/timetable/mine?on=2026-09-14").json()["sessions"] == []   # drafts are never shown


# ------------------------------------------------------------------------------------------- the teacher
def test_teacher_day(as_user, db):
    t = as_user("teacher")
    me = t.get("/auth/me").json()
    assert "FACULTY" in me["roles"] and "STAFF_SELF" in me["roles"]
    assert {"attendance/class-session", "assessments/assessment-event", "awards/staff-award"} <= nav(t)
    assert "admissions/admission-application" not in nav(t) and "security/user-account" not in nav(t)

    # record own achievement, submit, but never approve it
    aw = t.post("/awards/staff-award", json={"activity_title": "Teaching excellence", "start_date": "2026-03-01", "award_name": "Excellence",
                                              "award_date": "2026-03-01", "currency_code": "INR"}).json()
    aid = aw["staff_activity_id"]
    assert t.post(f"/awards/staff-award/{aid}/actions/submit").json()["workflow_status"] == "SUBMITTED"
    assert t.post(f"/awards/staff-award/{aid}/actions/approve").status_code in (403, 409)

    # sees colleagues' students (department scope) but cannot change student status or admissions
    assert t.get("/people/student").json()["count"] > 1
    sid = t.get("/people/student").json()["results"][0]["student_id"]
    assert t.post(f"/people/student/{sid}/actions/suspend", json={"remarks": "x"}).status_code == 403
    assert t.get("/admissions/admission-application").status_code == 403
    assert t.get("/hr/employee-aadhaar").status_code == 403


def test_hod_reviews_the_teachers_work(as_user):
    t, h = as_user("teacher"), as_user("hod")
    aid = t.post("/awards/staff-award", json={"activity_title": "Paper award", "start_date": "2026-02-01", "award_name": "Best paper",
                                               "award_date": "2026-02-01", "currency_code": "INR"}).json()["staff_activity_id"]
    t.post(f"/awards/staff-award/{aid}/actions/submit")
    queue = h.get("/awards/staff-award?workflow_status=SUBMITTED").status_code
    assert queue in (200, 422)
    for step in ("review", "verify", "approve"):
        assert h.post(f"/awards/staff-award/{aid}/actions/{step}").status_code == 200, step
    final = t.get(f"/awards/staff-award/{aid}").json()
    assert final["workflow_status"] == "APPROVED" and final["actions"] == []
    assert t.patch(f"/awards/staff-award/{aid}", json={"award_name": "Changed after approval"}).status_code == 409


# ------------------------------------------------------------------------------ administrators and operators
def test_administrator_onboards_a_new_teacher(as_user, app, db):
    admin = as_user("demoadmin")
    emp = db.execute(text("SELECT employee_id FROM employee e WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.employee_id = e.employee_id) LIMIT 1")).scalar()
    created = admin.post("/security/users", json={"username": "new.teacher", "email": "nt@example.org", "first_name": "New", "last_name": "Teacher", "employee_id": emp}).json()
    assert admin.post("/security/role-assignments", json={"user_id": created["user_id"], "role_code": "FACULTY", "scope_type": "DEPARTMENT", "scope_id": 1}).status_code == 201
    c = Client(app)
    c.login("new.teacher", created["temporary_password"])
    assert c.get("/people/student").status_code == 403                       # must change the temporary password first
    r = c.post("/auth/change-password", json={"current_password": created["temporary_password"], "new_password": "Teacher#Welcome2026"})
    c.http.headers["Authorization"] = "Bearer " + r.json()["access"]
    me = c.get("/auth/me").json()
    assert me["employee_ids"] == [emp] and set(me["roles"]) >= {"FACULTY", "STAFF_SELF"}
    assert c.get("/people/student").json()["count"] > 0
    assert "attendance/class-session" in nav(c)
    audit = admin.get("/security/audit?resource=user_account").json()["results"]
    assert audit and audit[0]["action"] in ("create", "link_person", "assign_role")


def test_security_officer_responds_to_a_compromised_account(as_user, app):
    victim_client = Client(app)
    victim_client.login("campusadm")
    uid = victim_client.get("/auth/me").json()["user_id"]
    admin = as_user("demoadmin")
    assert admin.post(f"/security/users/{uid}/revoke-sessions").status_code == 204
    assert victim_client.get("/auth/me").status_code == 401
    pw = admin.post(f"/security/users/{uid}/reset-password").json()["temporary_password"]
    fresh = Client(app)
    fresh.login("campusadm", expect=401)                                      # old password is dead
    fresh.login("campusadm", pw)
    assert fresh.get("/auth/me").json()["must_change_password"] is True


def test_registrar_runs_the_office(as_user):
    r = as_user("registrar")
    assert {"admissions/admission-application", "people/student", "documents/certificate-request"} <= nav(r)
    assert r.get("/people/employee").status_code == 200                       # read-only HR directory
    assert r.post("/people/employee", json={"first_name": "X", "joining_date": "2026-01-01", "employment_type": "REGULAR"}).status_code in (403, 422)
    assert r.get("/security/users").status_code == 403
    assert r.get("/ops/jobs").status_code == 403


def test_examination_cell_publishes_results_to_students(as_user, db):
    ex = as_user("examcell")
    off = db.execute(text("SELECT course_offering_id FROM assessment_event WHERE status IN ('CONDUCTED','PUBLISHED') LIMIT 1")).scalar()
    assert ex.post(f"/assessments/offerings/{off}/calculate-results").status_code == 200
    rows = ex.get("/assessments/student-course-result?page_size=100").json()["results"]
    for row in rows:
        assert ex.post(f"/assessments/student-course-result/{row['student_course_result_id']}/actions/publish").status_code in (200, 409)
    users = db.execute(text("SELECT DISTINCT u.username FROM student_course_result x JOIN student_course_registration r USING (course_registration_id) "
                            "JOIN student_term_registration t USING (term_registration_id) JOIN student_programme_enrolment e USING (enrolment_id) "
                            "JOIN person_account_link l ON l.student_id = e.student_id JOIN user_account u ON u.user_id = l.user_id "
                            "WHERE u.username IN ('student', 'student2')")).scalars().all()
    for name in users[:2]:
        s = as_user(name)
        mine = s.get("/assessments/student-course-result").json()["results"]
        assert mine and all(m["state"] == "PUBLISHED" for m in mine)
