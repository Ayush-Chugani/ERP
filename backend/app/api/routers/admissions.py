"""Admissions: fee clearance and the admit command that turns a selected application into a student + enrolment."""
from datetime import date

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import active_principal, client_ip
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.db.session import get_db
from app.models.admission_enrolment import (
    AdmissionApplicant,
    AdmissionFeeClearance,
    StudentProgrammeEnrolment,
)
from app.models.people_master import Student
from app.rbac.engine import Principal
from app.resources import crud, rules
from app.resources.registry import build_registry
from app.resources.router import _idem, _store
from app.services import audit

router = APIRouter(prefix="/admissions", tags=["Admissions"])


class ClearanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=1, max_length=150)


class AdmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    curriculum_scheme_id: int
    admission_semester_id: int
    admission_date: date
    expected_completion_date: date | None = None
    student_id: int | None = None   # link an existing student; omitted = create one from the applicant record


def _application(db: Session, principal: Principal, application_id: int, action: str, lock: bool = True):
    spec = build_registry()["admission_application"]
    obj = crud.get_one(db, spec, principal, application_id, action, lock=lock)
    if not principal.can(spec.perm_module, spec.perm_resource, action) and not principal.is_superuser:
        raise Forbidden()
    return obj


@router.post("/admission-application/{application_id}/clearance", status_code=201)
def record_clearance(application_id: int, body: ClearanceIn, request: Request,
                     principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Record that fees have been cleared for a selected application (authorised finance / admissions staff)."""
    app_row = _application(db, principal, application_id, "VERIFY")
    if app_row.application_status != "SELECTED":
        raise Conflict("Clearance can only be recorded for selected applications.")
    row = AdmissionFeeClearance(application_id=application_id, reference=body.reference.strip(),
                                application_version=app_row.version, actor_id=principal.user_id,
                                recorded_at=rules.datetime.now(rules.UTC))
    db.add(row)
    audit.record(db, principal, action="fee_clearance", module="ADMISSION", resource="admission_application",
                 record_id=application_id, after={"reference": row.reference},
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    return {"id": row.id, "application_id": application_id, "reference": row.reference}


@router.post("/admission-application/{application_id}/admit", status_code=201)
def admit(application_id: int, body: AdmitIn, request: Request, principal: Principal = Depends(active_principal),
          db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    replay, token = _idem(db, principal, request, idempotency_key, {"a": application_id, **body.model_dump(mode="json")})
    if replay is not None:
        return replay
    app_row = _application(db, principal, application_id, "APPROVE")
    if app_row.application_status != "SELECTED" or app_row.eligibility_status != "ELIGIBLE":
        raise Conflict("Only selected, eligible applications can be admitted.")
    cleared = db.execute(select(AdmissionFeeClearance.id).where(
        AdmissionFeeClearance.application_id == application_id,
        AdmissionFeeClearance.application_version == app_row.version)).first()
    if not cleared:
        raise Conflict("Fee clearance must be recorded before admission.", code="clearance_required")
    year_status = db.execute(text("SELECT status FROM academic_year WHERE academic_year_id = :y"),
                             {"y": app_row.academic_year_id}).scalar()
    programme = db.execute(text("SELECT is_active, programme_code FROM programme WHERE programme_id = :p"),
                           {"p": app_row.programme_id}).first()
    if year_status != "ACTIVE" or not programme or not programme[0]:
        raise Conflict("The admission year and programme must both be active.")
    scheme = db.execute(text(
        "SELECT status, effective_from, effective_to, programme_id FROM curriculum_scheme WHERE curriculum_scheme_id = :s"),
        {"s": body.curriculum_scheme_id}).first()
    if scheme is None or scheme[3] != app_row.programme_id:
        raise Invalid("The curriculum scheme must belong to the applied programme.")
    if scheme[0] != "ACTIVE" or scheme[1] > body.admission_date or (scheme[2] and scheme[2] < body.admission_date):
        raise Conflict("The curriculum scheme must be active on the admission date.")
    if body.expected_completion_date and body.expected_completion_date < body.admission_date:
        raise Invalid("Expected completion cannot be before the admission date.")

    applicant = db.scalar(select(AdmissionApplicant).where(
        AdmissionApplicant.admission_applicant_id == app_row.admission_applicant_id).with_for_update())
    if body.student_id is not None:
        student = db.get(Student, body.student_id)
        if student is None or student.institution_id != applicant.institution_id:
            raise Invalid("Unknown student for this institution.", details={"student_id": ["Invalid."]})
        if applicant.canonical_student_id and applicant.canonical_student_id != student.student_id:
            raise Conflict("The applicant is already linked to a different student.")
    else:
        if applicant.canonical_student_id:
            student = db.get(Student, applicant.canonical_student_id)
        else:
            student = Student(
                student_number=rules.next_number(db, "student", "student_number",
                                                 f"{programme[1]}{body.admission_date.year % 100:02d}", 4),
                first_name=applicant.first_name, middle_name=applicant.middle_name, last_name=applicant.last_name,
                display_name=applicant.display_name, date_of_birth=applicant.date_of_birth,
                primary_email=applicant.primary_email, primary_phone=applicant.primary_phone,
                admission_date=body.admission_date, student_status="ACTIVE", institution_id=applicant.institution_id,
                gender_id=applicant.gender_id, caste_id=applicant.caste_id, sub_caste_id=applicant.sub_caste_id,
                social_category_id=applicant.social_category_id, nationality_country_id=applicant.nationality_country_id)
            db.add(student)
            db.flush()
    if student.student_status in ("APPLICANT",):
        student.student_status = "ACTIVE"
    app_row.application_status = "ADMITTED"
    app_row.admitted_student_id = student.student_id
    app_row.version += 1
    app_row.updated_by_id = principal.user_id
    applicant.canonical_student_id = student.student_id
    applicant.version += 1
    applicant.updated_by_id = principal.user_id
    db.flush()
    enrolment = StudentProgrammeEnrolment(
        application_id=application_id, student_id=student.student_id, programme_id=app_row.programme_id,
        specialization_id=app_row.specialization_id, admission_academic_year_id=app_row.academic_year_id,
        admission_category_id=app_row.admission_category_id, curriculum_scheme_id=body.curriculum_scheme_id,
        admission_semester_id=body.admission_semester_id, admission_date=body.admission_date,
        expected_completion_date=body.expected_completion_date, enrolment_status="ACTIVE", version=1,
        created_by_id=principal.user_id, updated_by_id=principal.user_id)
    db.add(enrolment)
    db.flush()
    db.execute(text(
        "INSERT INTO enrolment_status_history (enrolment_id, actor_id, old_status, new_status, sequence_number, "
        "effective_date, reason, source, request_id) VALUES (:e, :a, NULL, 'ACTIVE', 1, :d, 'Admission approved', 'command', :r)"),
        {"e": enrolment.enrolment_id, "a": principal.user_id, "d": body.admission_date, "r": request.state.request_id})
    audit.status_change(db, principal, "admission_application", application_id, "SELECTED", "ADMITTED", "admit")
    audit.record(db, principal, action="admit", module="ADMISSION", resource="admission_application",
                 record_id=application_id,
                 after={"student_id": student.student_id, "enrolment_id": enrolment.enrolment_id},
                 request_id=request.state.request_id, ip=client_ip(request), institution_id=applicant.institution_id)
    result = {"application_id": application_id, "student_id": student.student_id,
              "student_number": student.student_number, "enrolment_id": enrolment.enrolment_id}
    _store(db, principal, request, token, result)
    db.commit()
    return result


@router.get("/admission-application/{application_id}/summary")
def summary(application_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Everything a reviewer needs to decide: applicant, clearance state and what the next step is."""
    spec = build_registry()["admission_application"]
    obj = crud.get_one(db, spec, principal, application_id)
    applicant = db.get(AdmissionApplicant, obj.admission_applicant_id)
    cleared = bool(db.execute(select(AdmissionFeeClearance.id).where(
        AdmissionFeeClearance.application_id == application_id,
        AdmissionFeeClearance.application_version == obj.version)).first())
    if obj.admitted_student_id is None and obj.application_status == "SELECTED":
        next_step = "admit" if cleared else "record_clearance"
    else:
        next_step = None
    enrol = db.scalar(select(StudentProgrammeEnrolment.enrolment_id).where(
        StudentProgrammeEnrolment.application_id == application_id))
    if applicant is None:
        raise NotFound()
    return {"application_id": application_id, "status": obj.application_status, "eligibility": obj.eligibility_status,
            "applicant": {"name": applicant.display_name, "email": applicant.primary_email,
                          "phone": applicant.primary_phone},
            "fee_cleared": cleared, "next_step": next_step, "student_id": obj.admitted_student_id,
            "enrolment_id": enrol}
