"""Edge cases of the resource engine and the business rules attached to it."""

import pytest
from sqlalchemy import select, text

from app.core.errors import Forbidden, NotFound
from app.models.accounts import UserAccount
from app.rbac.engine import load_principal
from app.resources import crud
from app.resources.registry import build_registry


def principal_of(db, username):
    return load_principal(db, db.scalar(select(UserAccount).where(UserAccount.username == username)))


class Body:
    def __init__(self, **data):
        self._d = data

    def model_dump(self, exclude_unset=True, **_):
        return dict(self._d)


# ------------------------------------------------------------------------------------------- list filters
@pytest.mark.parametrize("query,status", [
    ("student_id__gte=1&student_id__lte=1000", 200), ("student_id__gt=0&student_id__lt=99999", 200), ("student_id__ne=1", 200),
    ("date_of_birth__gte=1990-01-01", 200), ("date_of_birth__gte=notadate", 422), ("created_at__gte=2020-01-01T00:00:00Z", 200),
    ("created_at__lte=2100-01-01T00:00:00", 200), ("created_at__gte=garbage", 422), ("student_number__contains=FE24", 200),
    ("student_number__startswith=01FE", 200), ("student_number__contains=%25", 200), ("primary_email__isnull=true", 200),
    ("primary_email__isnull=0", 200), ("student_status__in=ACTIVE,APPLICANT", 200), ("student_id=abc", 422), ("student_id__in=1,x", 422),
    ("student_number__weird=1", 422), ("page=0", 200), ("page_size=500", 200), ("page_size=0", 200), ("ordering=-student_id,display_name", 200),
    ("ordering=nonexistent", 422),
])
def test_student_list_filters(as_user, query, status):
    assert as_user("registrar").get(f"/people/student?{query}").status_code == status


def test_boolean_decimal_and_time_filters(as_user):
    a = as_user("demoadmin")
    for q in ("is_active=true", "is_active=1", "is_active=no", "is_active=0", "is_active=yes"):
        assert a.get(f"/reference/gender?{q}").status_code == 200
    assert a.get("/reference/gender?is_active=maybe").status_code == 422
    assert a.get("/curriculum/course-catalog?credits__gte=2.5").status_code == 200
    assert a.get("/curriculum/course-catalog?credits__gte=abc").status_code == 422
    assert a.get("/calendar/time-slot?start_time__gte=09:00:00").status_code == 200
    assert a.get("/calendar/time-slot?start_time__gte=nine").status_code == 422


# ----------------------------------------------------------------------------------------- engine guards
def test_engine_refuses_writes_on_read_only_and_undeletable_resources(db):
    reg = build_registry()
    p = principal_of(db, "demoadmin")
    with pytest.raises(Forbidden):
        crud.create_row(db, reg["login_audit"], p, Body(), {})
    with pytest.raises(Forbidden):
        crud.update_row(db, reg["login_audit"], p, 1, Body(), {})
    with pytest.raises(Forbidden):
        crud.delete_row(db, reg["login_audit"], p, 1, {})


def test_self_service_users_cannot_create_or_delete_arbitrary_records(db):
    reg = build_registry()
    p = principal_of(db, "student")
    with pytest.raises(Forbidden):
        crud.create_row(db, reg["gender"], p, Body(gender_code="Q", gender_name="Q"), {})
    with pytest.raises(Forbidden):
        crud.delete_row(db, reg["student_address"], p, 1, {})


def test_unknown_transition_and_missing_prerequisite(as_user, db):
    admin = as_user("demoadmin")
    sid = admin.get("/people/student?page_size=1").json()["results"][0]["student_id"]
    assert admin.post(f"/people/student/{sid}/actions/nonexistent").status_code == 404
    reg = build_registry()
    p = principal_of(db, "demoadmin")
    spec = reg["student"]
    with pytest.raises(NotFound):
        crud.run_transition(db, spec, p, sid, "does_not_exist", None, {})


def test_status_cannot_be_patched_directly(as_user):
    a = as_user("demoadmin")
    sid = a.get("/people/student?page_size=1").json()["results"][0]["student_id"]
    assert a.patch(f"/people/student/{sid}", json={"student_status": "ALUMNUS"}).status_code == 422


def test_empty_strings_become_null_and_required_fields_cannot_be_blanked(as_user):
    a = as_user("demoadmin")
    created = a.post("/reference/religion", json={"religion_code": "TST", "religion_name": "Test", }).json()
    rid = created["religion_id"]
    assert a.patch(f"/reference/religion/{rid}", json={"religion_code": "  "}).json()["religion_code"] is None
    assert a.patch(f"/reference/religion/{rid}", json={"religion_name": None}).status_code == 422
    assert a.patch(f"/reference/religion/{rid}", json={"religion_name": "   "}).status_code == 422


def test_versioned_update_conflicts_and_increments(as_user, db):
    a = as_user("demoadmin")
    row = a.get("/admissions/admission-applicant?page_size=1").json()["results"][0]
    pk = row["admission_applicant_id"]
    assert a.patch(f"/admissions/admission-applicant/{pk}", json={"version": row["version"] + 5, "first_name": "Z"}).status_code == 409
    ok = a.patch(f"/admissions/admission-applicant/{pk}", json={"version": row["version"], "primary_phone": "9111122222"})
    assert ok.status_code == 200 and ok.json()["version"] == row["version"] + 1
    assert a.patch(f"/admissions/admission-applicant/{pk}", json={"primary_phone": "9111133333"}, headers={"If-Match": '"999"'}).status_code == 409
    assert a.patch(f"/admissions/admission-applicant/{pk}", json={"primary_phone": "9111144444"}, headers={"If-Match": "garbage"}).status_code == 200


def test_missing_required_values_listed_together(as_user):
    r = as_user("demoadmin").post("/people/student", json={"institution_id": 1})
    assert r.status_code == 422 and r.json()["error"]["details"]


# ----------------------------------------------------------------------------------- numbering and defaults
def test_student_and_employee_numbers_and_names_are_generated(as_user, db):
    reg = as_user("registrar")
    s = reg.post("/people/student", json={"first_name": "Gita", "last_name": "Rao", "institution_id": 1}).json()
    assert s["display_name"] == "Gita Rao" and s["student_number"].startswith("S26")
    s2 = reg.post("/people/student", json={"first_name": "Hari", "institution_id": 1}).json()
    assert s2["student_number"] != s["student_number"]
    assert reg.post("/people/student", json={"institution_id": 1}).status_code == 422                 # no name at all
    meta = reg.get("/meta/people/employee").json()
    ch = {c["name"]: c["choices"] for c in meta["columns"] if c["choices"]}
    src = db.execute(text("SELECT employment_source_id FROM employment_source LIMIT 1")).scalar()
    e = as_user("demoadmin").post("/people/employee", json={"first_name": "Indu", "joining_date": "2026-01-05", "employment_type": ch["employment_type"][0],
                                                            "institution_id": 1, "employment_source_id": src})
    assert e.status_code == 201 and e.json()["employee_number"].startswith("E") and e.json()["display_name"] == "Indu"


def test_application_requires_open_academic_year(as_user, db):
    reg = as_user("registrar")
    closed = db.execute(text("SELECT academic_year_id FROM academic_year LIMIT 1")).scalar()
    db.execute(text("UPDATE academic_year SET status = 'CLOSED' WHERE academic_year_id = :y"), {"y": closed})
    db.commit()
    applicant = db.execute(text("SELECT admission_applicant_id FROM admission_applicant LIMIT 1")).scalar()
    prog = db.execute(text("SELECT programme_id FROM programme LIMIT 1")).scalar()
    r = reg.post("/admissions/admission-application", json={"admission_applicant_id": applicant, "programme_id": prog, "academic_year_id": closed})
    assert r.status_code == 409


def test_certificate_and_grievance_need_a_student_for_non_students(as_user, db):
    reg = as_user("registrar")
    ctype = db.execute(text("SELECT certificate_type_id FROM certificate_type LIMIT 1")).scalar()
    r = reg.post("/documents/certificate-request", json={"certificate_type_id": ctype})
    assert r.status_code == 422 and "student_id" in r.json()["error"]["details"]
    sid = reg.get("/people/student?page_size=1").json()["results"][0]["student_id"]
    assert reg.post("/documents/certificate-request", json={"certificate_type_id": ctype, "student_id": sid}).status_code == 201


# ----------------------------------------------------------------------------------- registration rules
@pytest.fixture()
def reg_setup(db):
    """An active enrolment with a course offering in a term of its programme and no registration yet (made free if needed)."""
    row = db.execute(text(
        "SELECT e.enrolment_id, e.programme_id, p.programme_term_offering_id, o.course_offering_id FROM student_programme_enrolment e "
        "JOIN programme_term_offering p ON p.programme_id = e.programme_id JOIN course_offering o ON o.programme_term_offering_id = p.programme_term_offering_id "
        "WHERE e.enrolment_status = 'ACTIVE' ORDER BY e.enrolment_id LIMIT 1")).first()
    if row is None:
        pytest.skip("no enrolment with an offered course")
    t = {"e": row.enrolment_id, "p": row.programme_term_offering_id}
    regs = "SELECT term_registration_id FROM student_term_registration WHERE enrolment_id = :e AND programme_term_offering_id = :p"
    crs = f"SELECT course_registration_id FROM student_course_registration WHERE term_registration_id IN ({regs})"
    db.execute(text(f"DELETE FROM course_offering_section_student WHERE course_registration_id IN ({crs})"), t)
    db.execute(text(f"DELETE FROM student_course_registration WHERE term_registration_id IN ({regs})"), t)
    db.execute(text("DELETE FROM student_term_registration WHERE enrolment_id = :e AND programme_term_offering_id = :p"), t)
    db.commit()
    return row


def test_term_registration_rules(as_user, db, reg_setup):
    admin = as_user("demoadmin")
    body = {"enrolment_id": reg_setup.enrolment_id, "programme_term_offering_id": reg_setup.programme_term_offering_id}
    db.execute(text("UPDATE programme_term_offering SET status='PLANNED' WHERE programme_term_offering_id=:p"), {"p": reg_setup.programme_term_offering_id})
    db.commit()
    assert admin.post("/registration/student-term-registration", json=body).status_code == 409           # registration not open
    other_programme = db.execute(text("SELECT programme_term_offering_id FROM programme_term_offering WHERE programme_id <> :p LIMIT 1"), {"p": reg_setup.programme_id}).scalar()
    if other_programme:
        assert admin.post("/registration/student-term-registration", json={**body, "programme_term_offering_id": other_programme}).status_code == 422
    db.execute(text("UPDATE programme_term_offering SET status='REGISTRATION_OPEN' WHERE programme_term_offering_id=:p"), {"p": reg_setup.programme_term_offering_id})
    db.execute(text("UPDATE student_programme_enrolment SET enrolment_status='ON_BREAK' WHERE enrolment_id=:e"), {"e": reg_setup.enrolment_id})
    db.commit()
    assert admin.post("/registration/student-term-registration", json=body).status_code == 409           # enrolment not active
    db.execute(text("UPDATE student_programme_enrolment SET enrolment_status='ACTIVE' WHERE enrolment_id=:e"), {"e": reg_setup.enrolment_id})
    db.commit()
    term = admin.post("/registration/student-term-registration", json=body)
    assert term.status_code == 201
    tid = term.json()["term_registration_id"]
    course_body = {"term_registration_id": tid, "course_offering_id": reg_setup.course_offering_id}
    db.execute(text("UPDATE course_offering SET status='PLANNED' WHERE course_offering_id=:o"), {"o": reg_setup.course_offering_id})
    db.commit()
    assert admin.post("/registration/student-course-registration", json=course_body).status_code == 409   # course not open
    db.execute(text("UPDATE course_offering SET status='OPEN', registration_capacity=NULL WHERE course_offering_id=:o"), {"o": reg_setup.course_offering_id})
    db.commit()
    assert admin.post("/registration/student-course-registration", json=course_body).status_code == 201
    assert admin.post("/registration/student-course-registration", json=course_body).status_code == 409   # already registered
    other = db.execute(text("SELECT enrolment_id FROM student_programme_enrolment WHERE programme_id=:p AND enrolment_id<>:e AND enrolment_status='ACTIVE' LIMIT 1"),
                       {"p": reg_setup.programme_id, "e": reg_setup.enrolment_id}).scalar()
    if other:
        db.execute(text("DELETE FROM student_term_registration WHERE enrolment_id=:e AND programme_term_offering_id=:p AND NOT EXISTS (SELECT 1 FROM student_course_registration r WHERE r.term_registration_id = student_term_registration.term_registration_id)"),
                   {"e": other, "p": reg_setup.programme_term_offering_id})
        db.commit()
        t2 = admin.post("/registration/student-term-registration", json={"enrolment_id": other, "programme_term_offering_id": reg_setup.programme_term_offering_id})
        if t2.status_code == 201:
            db.execute(text("UPDATE course_offering SET registration_capacity=1 WHERE course_offering_id=:o"), {"o": reg_setup.course_offering_id})
            db.commit()
            full = admin.post("/registration/student-course-registration", json={"term_registration_id": t2.json()["term_registration_id"], "course_offering_id": reg_setup.course_offering_id})
            assert full.status_code == 409                                                                    # capacity reached
    assert admin.post("/registration/student-course-registration", json={"term_registration_id": tid, "course_offering_id": 99999999}).status_code == 422
    foreign = db.execute(text("SELECT course_offering_id FROM course_offering WHERE programme_term_offering_id <> :p LIMIT 1"), {"p": reg_setup.programme_term_offering_id}).scalar()
    if foreign:
        assert admin.post("/registration/student-course-registration", json={"term_registration_id": tid, "course_offering_id": foreign}).status_code == 422
    # credit limits
    db.execute(text("INSERT INTO registration_policy (programme_id, minimum_credits, maximum_credits, version, updated_by_id) VALUES (:p, 500, 600, 1, 1)"), {"p": reg_setup.programme_id})
    db.commit()
    low = admin.post(f"/registration/student-term-registration/{tid}/actions/submit")
    assert low.status_code == 409 and low.json()["error"]["code"] == "credit_limits"
    db.execute(text("DELETE FROM registration_policy WHERE programme_id=:p"), {"p": reg_setup.programme_id})
    db.commit()
    assert admin.post(f"/registration/student-term-registration/{tid}/actions/submit").status_code == 200
    db.execute(text("UPDATE student_term_registration SET registration_status='DRAFT' WHERE term_registration_id=:t"), {"t": tid})
    db.commit()
    assert admin.post("/registration/student-course-registration", json={"term_registration_id": tid, "course_offering_id": reg_setup.course_offering_id}).status_code == 409


def test_course_added_to_a_cancelled_term_is_refused(as_user, db, reg_setup):
    admin = as_user("demoadmin")
    db.execute(text("UPDATE programme_term_offering SET status='REGISTRATION_OPEN' WHERE programme_term_offering_id=:p"), {"p": reg_setup.programme_term_offering_id})
    db.execute(text("UPDATE course_offering SET status='OPEN' WHERE course_offering_id=:o"), {"o": reg_setup.course_offering_id})
    db.commit()
    tid = admin.post("/registration/student-term-registration", json={"enrolment_id": reg_setup.enrolment_id, "programme_term_offering_id": reg_setup.programme_term_offering_id}).json()["term_registration_id"]
    assert admin.post(f"/registration/student-term-registration/{tid}/actions/cancel", json={"remarks": "no"}).status_code == 200
    assert admin.post("/registration/student-course-registration", json={"term_registration_id": tid, "course_offering_id": reg_setup.course_offering_id}).status_code == 409


def test_evidence_document_gets_default_statuses(as_user, db):
    t = as_user("teacher")
    aw = t.post("/awards/staff-award", json={"activity_title": "Evidence host", "start_date": "2026-02-02", "award_name": "A", "award_date": "2026-02-02", "currency_code": "INR"}).json()
    dt = db.execute(text("SELECT document_type_id FROM document_type LIMIT 1")).scalar()
    cl = db.execute(text("SELECT confidentiality_level_id FROM confidentiality_level LIMIT 1")).scalar()
    r = t.post("/evidence/evidence-document", json={"staff_activity_id": aw["staff_activity_id"], "document_type_id": dt, "confidentiality_level_id": cl, "document_title": "Certificate scan"})
    assert r.status_code == 201, r.text
    assert r.json()["workflow_status"] == "DRAFT"
    assert {a["name"] for a in r.json()["actions"]} >= {"submit"}


# ----------------------------------------------------------------- create every creatable resource (smoke)
def _payload(client, meta):
    body = {}
    for c in meta["columns"]:
        if c["readonly"] or c["primary"] or not c["required"]:
            continue
        if c["references"]:
            res = client.get(f"/lookups/{c['references']['path']}?limit=1").json().get("results") or []
            body[c["name"]] = res[0]["id"] if res else 1
        elif c["choices"]:
            body[c["name"]] = c["choices"][0]
        else:
            k = c["kind"]
            body[c["name"]] = {"int": 1, "bool": True, "date": "2026-01-15", "datetime": "2026-01-15T10:00:00Z", "time": "10:00:00",
                               "decimal": "10.50", "json": {}, "text": "text"}.get(k, "x" * min(c["max_length"] or 8, 8))
    return body


def test_every_creatable_resource_creates_or_fails_cleanly(as_user):
    admin = as_user("demoadmin")
    created = 0
    for g in admin.get("/meta").json()["groups"]:
        for r in g["resources"]:
            if not r["can"]["create"]:
                continue
            meta = admin.get(f"/meta/{r['path']}").json()
            res = admin.post(f"/{r['path']}", json=_payload(admin, meta))
            assert res.status_code in (201, 403, 404, 409, 422), (r["path"], res.status_code, res.text[:200])
            if res.status_code == 201:
                created += 1
                pk = res.json().get(meta["primary_key"])
                assert admin.get(f"/{r['path']}/{pk}").status_code == 200
                assert admin.delete(f"/{r['path']}/{pk}").status_code in (204, 403, 409)
    assert created > 40
