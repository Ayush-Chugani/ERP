"""Cross-module business rules: timetable clashes, registration limits, certificates, grievances, announcements, expiry jobs."""
import pytest
from sqlalchemy import text

from app.worker.runner import run_one


def drain(limit=50):
    n = 0
    while n < limit and run_one("test", ["default"]):
        n += 1
    return n


def test_timetable_clash_detection(as_user, db):
    row = db.execute(text("SELECT * FROM timetable_session ORDER BY timetable_session_id LIMIT 1")).mappings().first()
    if row is None:
        pytest.skip("no timetable sessions in demo data")
    admin = as_user("demoadmin")
    keys = ("day_of_week", "effective_from", "effective_to", "course_offering_section_id", "faculty_assignment_id",
            "revision_id", "room_id", "time_slot_id")
    clash = {k: (str(row[k]) if hasattr(row[k], "isoformat") else row[k]) for k in keys}
    r = admin.post("/timetable/timetable-session", json=clash)
    assert r.status_code == 409 and r.json()["error"]["code"] == "timetable_clash", r.text


def test_certificate_request_to_issue_flow(as_user, db):
    student = as_user("student")
    ctype = db.execute(text("SELECT certificate_type_id FROM certificate_type LIMIT 1")).scalar()
    r = student.post("/documents/certificate-request", json={"certificate_type_id": ctype, "purpose": "Bank loan"})
    assert r.status_code == 201, r.text
    req = r.json()
    rid = req["certificate_request_id"]
    assert req["request_number"].startswith("CR-") and req["request_status"] == "SUBMITTED"
    base = f"/documents/certificate-request/{rid}"
    assert student.post(f"{base}/actions/approve").status_code in (403, 409)
    reg = as_user("registrar")
    assert reg.post(f"{base}/actions/issue").status_code == 409                 # must be approved first
    assert reg.post(f"{base}/actions/start_review").status_code == 200
    assert reg.post(f"{base}/actions/approve").status_code == 200
    issued = reg.post(f"{base}/actions/issue")
    assert issued.status_code == 200 and issued.json()["certificate_number"].startswith("CERT-")
    drain()
    assert any("certificate" in n["title"].lower() for n in student.get("/notifications").json()["results"])
    assert student.post(f"{base}/actions/cancel").status_code == 409


def test_grievance_lifecycle_logs_actions_and_notifies(as_user, db):
    student = as_user("student")
    cat = db.execute(text("SELECT grievance_category_id FROM grievance_category LIMIT 1")).scalar()
    r = student.post("/support/grievance", json={"grievance_category_id": cat, "subject": "Lab access",
                                                 "description": "Cannot enter the lab"})
    assert r.status_code == 201, r.text
    gid = r.json()["grievance_id"]
    officer = as_user("support")
    base = f"/support/grievance/{gid}"
    assert officer.post(f"{base}/actions/assign").status_code == 200
    assert officer.post(f"{base}/actions/start_review").status_code == 200
    assert officer.post(f"{base}/actions/resolve").status_code == 422           # resolution required
    done = officer.post(f"{base}/actions/resolve", json={"remarks": "Access card issued"})
    assert done.status_code == 200 and done.json()["resolution"] == "Access card issued" and done.json()["resolved_at"]
    log = db.execute(text("SELECT action_type FROM grievance_action WHERE grievance_id=:g ORDER BY grievance_action_id"),
                     {"g": gid}).scalars().all()
    assert log == ["ASSIGN", "START_REVIEW", "RESOLVE"]
    assert student.get(f"{base}/history").json()["results"]
    drain()
    assert student.get("/notifications").json()["count"] >= 1
    assert as_user("student2").get(f"{base}").status_code == 404                   # other students never see it


def test_announcement_delivery_through_the_queue(as_user, db):
    reg = as_user("registrar")
    atype = db.execute(text("SELECT announcement_type_id FROM announcement_type LIMIT 1")).scalar()
    r = reg.post("/communication/announcement", json={
        "announcement_type_id": atype, "title": "Holiday", "description": "Campus closed Friday",
        "publish_from": "2026-01-01T00:00:00Z", "audience_type": "STUDENTS"})
    assert r.status_code == 201, r.text
    aid = r.json()["announcement_id"]
    assert reg.post(f"/communication/announcement/{aid}/actions/submit").status_code == 200
    assert reg.post(f"/communication/announcement/{aid}/actions/approve").status_code == 200
    assert drain() >= 1
    assert as_user("student").get("/notifications").json()["count"] >= 1


def test_expiry_jobs(db):
    from app.worker.handlers import documents_expire, evidence_expiry, memberships_expire

    assert memberships_expire(db, {})["expired"] >= 0
    assert documents_expire(db, {})["expired"] >= 0
    assert evidence_expiry(db, {})["notices"] >= 0


def test_duplicate_course_registration_is_refused(as_user, db):
    row = db.execute(text(
        "SELECT r.term_registration_id, r.course_offering_id, u.username FROM student_course_registration r "
        "JOIN student_term_registration t USING (term_registration_id) "
        "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
        "JOIN person_account_link l ON l.student_id = e.student_id JOIN user_account u ON u.user_id = l.user_id "
        "WHERE r.registration_status IN ('REGISTERED','APPROVED') LIMIT 1")).first()
    if row is None:
        pytest.skip("no linked student registration")
    student = as_user(row.username)
    r = student.post("/registration/student-course-registration",
                     json={"term_registration_id": row.term_registration_id, "course_offering_id": row.course_offering_id})
    assert r.status_code in (409, 403, 422), r.text
