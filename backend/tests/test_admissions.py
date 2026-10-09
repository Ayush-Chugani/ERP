"""Admissions pipeline: application -> review -> selection -> fee clearance -> admission (student + enrolment)."""
import pytest
from sqlalchemy import text


@pytest.fixture()
def setup(db):
    row = db.execute(text(
        "SELECT cs.curriculum_scheme_id, cs.programme_id, cs.effective_from, y.academic_year_id, i.institution_id "
        "FROM curriculum_scheme cs JOIN programme p ON p.programme_id = cs.programme_id AND p.is_active "
        "JOIN academic_year y ON y.status = 'ACTIVE' JOIN department d ON d.department_id = p.department_id "
        "JOIN campus c ON c.campus_id = d.campus_id JOIN institution i ON i.institution_id = c.institution_id "
        "WHERE cs.status = 'ACTIVE' LIMIT 1")).first()
    if row is None:
        pytest.skip("demo data has no active scheme/year")
    sem = db.execute(text("SELECT semester_id FROM semester LIMIT 1")).scalar()
    return {"scheme": row[0], "programme": row[1], "from": row[2], "year": row[3], "inst": row[4], "sem": sem}


def test_full_admission_flow(as_user, setup):
    reg = as_user("registrar")
    applicant = reg.post("/admissions/admission-applicant", json={
        "first_name": "Asha", "last_name": "Verma", "primary_email": "asha.verma@example.org",
        "institution_id": setup["inst"]})
    assert applicant.status_code == 201, applicant.text
    assert applicant.json()["display_name"] == "Asha Verma"
    app = reg.post("/admissions/admission-application", json={
        "admission_applicant_id": applicant.json()["admission_applicant_id"], "programme_id": setup["programme"],
        "academic_year_id": setup["year"]})
    assert app.status_code == 201, app.text
    a = app.json()
    aid = a["application_id"]
    assert a["application_number"].startswith("APP-") and a["application_status"] == "DRAFT"

    base = f"/admissions/admission-application/{aid}"
    assert reg.post(f"{base}/actions/select").status_code == 409                    # cannot skip steps
    for step in ("submit", "start_review", "mark_eligible", "select"):
        r = reg.post(f"{base}/actions/{step}")
        assert r.status_code == 200, (step, r.text)
    assert reg.get(f"{base}/summary").json()["next_step"] == "record_clearance"
    admit_body = {"curriculum_scheme_id": setup["scheme"], "admission_semester_id": setup["sem"],
                  "admission_date": str(max(setup["from"], __import__("datetime").date.today()))}
    r = reg.post(f"{base}/admit", json=admit_body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "clearance_required"
    assert reg.post(f"{base}/clearance", json={"reference": "RCPT-001"}).status_code == 201
    r = reg.post(f"{base}/admit", json=admit_body, headers={"Idempotency-Key": "adm-1"})
    assert r.status_code == 201, r.text
    out = r.json()
    again = reg.post(f"{base}/admit", json=admit_body, headers={"Idempotency-Key": "adm-1"})
    assert again.json() == out                                                       # idempotent replay
    assert reg.post(f"{base}/admit", json=admit_body).status_code == 409             # already admitted
    student = reg.get(f"/people/student/{out['student_id']}").json()
    assert student["display_name"] == "Asha Verma" and student["student_status"] == "ACTIVE"
    assert reg.get(f"/admissions/student-programme-enrolment/{out['enrolment_id']}").json()["enrolment_status"] == "ACTIVE"
    assert reg.get(f"{base}").json()["application_status"] == "ADMITTED"


def test_students_cannot_admit_or_clear(as_user, setup):
    st = as_user("student")
    assert st.post("/admissions/admission-application/1/admit", json={
        "curriculum_scheme_id": 1, "admission_semester_id": 1, "admission_date": "2026-08-01"}).status_code in (403, 404)
    assert st.post("/admissions/admission-application/1/clearance", json={"reference": "x"}).status_code in (403, 404)
