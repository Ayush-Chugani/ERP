"""Business rules attached to the generic resource engine: automatic numbering, defaults and integrity checks that
need more than the schema can express. Hooks run inside the request transaction and raise AppError to veto."""
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.rbac.engine import Principal
from app.resources.spec import ResourceSpec

Hook = Callable[[Session, Principal, dict], None]
BEFORE_CREATE: dict[str, list[Hook]] = {}
AFTER_CREATE: dict[str, list[Callable[[Session, Principal, Any], None]]] = {}

# Columns the server fills in, so callers may omit them.
AUTO_FIELDS: dict[str, tuple[str, ...]] = {
    "student": ("student_number", "display_name"),
    "employee": ("employee_number", "display_name"),
    "admission_applicant": ("display_name",),
    "admission_application": ("application_number", "application_date"),
    "certificate_request": ("request_number", "student_id"),
    "grievance": ("grievance_number", "student_id"),
    "student_term_registration": ("registration_date", "programme_id"),
    "student_course_registration": ("registration_date", "registration_type", "programme_term_offering_id"),
    "attendance_correction_request": ("attendance_version", "old_status_id", "requested_at"),
}
INITIAL_ENUM = {("student_course_registration", "registration_type")}


def before_create(table: str):
    def deco(fn: Hook) -> Hook:
        BEFORE_CREATE.setdefault(table, []).append(fn)
        return fn
    return deco


def after_create(table: str):
    def deco(fn):
        AFTER_CREATE.setdefault(table, []).append(fn)
        return fn
    return deco


def run_before_create(spec: ResourceSpec, db: Session, principal: Principal, data: dict) -> None:
    for fn in BEFORE_CREATE.get(spec.table, []):
        fn(db, principal, data)


def run_after_create(spec: ResourceSpec, db: Session, principal: Principal, obj: Any) -> None:
    for fn in AFTER_CREATE.get(spec.table, []):
        fn(db, principal, obj)


def today() -> date:
    return datetime.now(UTC).date()


def next_number(db: Session, table: str, column: str, prefix: str, width: int = 5) -> str:
    """Race-safe sequential number (serialised per table with an advisory lock)."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"{table}.{column}"})
    count = db.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0
    n = count + 1
    while True:
        candidate = f"{prefix}{n:0{width}d}"
        if not db.execute(text(f"SELECT 1 FROM {table} WHERE {column} = :v"), {"v": candidate}).first():
            return candidate
        n += 1


def own_student_id(principal: Principal) -> int | None:
    return next(iter(principal.student_ids)) if len(principal.student_ids) == 1 else None


def _compose_display_name(data: dict) -> None:
    if not data.get("display_name"):
        parts = [data.get("first_name"), data.get("middle_name"), data.get("last_name")]
        data["display_name"] = " ".join(p for p in parts if p)
        if not data["display_name"]:
            raise Invalid("A name is required.", details={"first_name": ["Required."]})


@before_create("student")
def _student(db, principal, data):
    _compose_display_name(data)
    if not data.get("student_number"):
        data["student_number"] = next_number(db, "student", "student_number", f"S{today().year % 100:02d}")


@before_create("employee")
def _employee(db, principal, data):
    _compose_display_name(data)
    if not data.get("employee_number"):
        data["employee_number"] = next_number(db, "employee", "employee_number", "E")


@before_create("admission_applicant")
def _applicant(db, principal, data):
    _compose_display_name(data)


@before_create("admission_application")
def _application(db, principal, data):
    data.setdefault("application_date", today())
    if not data.get("application_number"):
        data["application_number"] = next_number(db, "admission_application", "application_number",
                                                 f"APP-{today().year}-")
    year = db.execute(text("SELECT status FROM academic_year WHERE academic_year_id = :y"),
                      {"y": data.get("academic_year_id")}).scalar()
    if year not in ("PLANNED", "ACTIVE"):
        raise Conflict("Applications can only be created for a planned or active academic year.")


def _default_student(principal: Principal, data: dict) -> None:
    if data.get("student_id") is None:
        sid = own_student_id(principal)
        if sid is None:
            raise Invalid("Choose the student this belongs to.", details={"student_id": ["Required."]})
        data["student_id"] = sid


@before_create("certificate_request")
def _certificate(db, principal, data):
    _default_student(principal, data)
    if not data.get("request_number"):
        data["request_number"] = next_number(db, "certificate_request", "request_number", f"CR-{today().year}-")


@before_create("grievance")
def _grievance(db, principal, data):
    _default_student(principal, data)
    if not data.get("grievance_number"):
        data["grievance_number"] = next_number(db, "grievance", "grievance_number", f"GR-{today().year}-")


@before_create("student_term_registration")
def _term_registration(db, principal, data):
    row = db.execute(text(
        "SELECT e.programme_id, e.enrolment_status, p.status FROM student_programme_enrolment e, programme_term_offering p "
        "WHERE e.enrolment_id = :e AND p.programme_term_offering_id = :p AND p.programme_id = e.programme_id"),
        {"e": data.get("enrolment_id"), "p": data.get("programme_term_offering_id")}).first()
    if row is None:
        raise Invalid("The enrolment and the term offering must belong to the same programme.")
    programme_id, enrolment_status, term_status = row
    if enrolment_status != "ACTIVE":
        raise Conflict("Only students with an active enrolment can register.")
    if term_status not in ("REGISTRATION_OPEN", "ACTIVE"):
        raise Conflict("Registration is not open for this term.")
    data["programme_id"] = programme_id
    data.setdefault("registration_date", today())


@before_create("student_course_registration")
def _course_registration(db, principal, data):
    row = db.execute(text(
        "SELECT t.programme_term_offering_id, t.registration_status, o.status, o.registration_capacity, "
        "o.programme_term_offering_id FROM student_term_registration t, course_offering o "
        "WHERE t.term_registration_id = :t AND o.course_offering_id = :o"),
        {"t": data.get("term_registration_id"), "o": data.get("course_offering_id")}).first()
    if row is None:
        raise Invalid("Unknown term registration or course offering.")
    term_offering, reg_status, offering_status, capacity, offering_term = row
    if term_offering != offering_term:
        raise Invalid("The course is not offered in the term this registration belongs to.")
    if reg_status not in ("DRAFT", "REGISTERED"):
        raise Conflict("Courses can only be added while the term registration is in draft or registered.")
    if offering_status not in ("OPEN", "ACTIVE"):
        raise Conflict("This course is not open for registration.")
    if db.execute(text(
            "SELECT 1 FROM student_course_registration WHERE term_registration_id = :t AND course_offering_id = :o "
            "AND registration_status NOT IN ('DROPPED','WITHDRAWN')"),
            {"t": data["term_registration_id"], "o": data["course_offering_id"]}).first():
        raise Conflict("The student is already registered for this course.")
    if capacity is not None:
        taken = db.execute(text(
            "SELECT count(*) FROM student_course_registration WHERE course_offering_id = :o "
            "AND registration_status NOT IN ('DROPPED','WITHDRAWN')"), {"o": data["course_offering_id"]}).scalar()
        if taken >= capacity:
            raise Conflict("This course has reached its registration capacity.")
    data["programme_term_offering_id"] = offering_term
    data.setdefault("registration_date", today())


def registration_credit_guard(db: Session, principal: Principal, obj: Any) -> None:
    """A term registration may only be submitted/approved when its credits sit inside the programme's limits."""
    credits = db.execute(text(
        "SELECT COALESCE(SUM(c.credits), 0) FROM student_course_registration r "
        "JOIN course_offering o ON o.course_offering_id = r.course_offering_id "
        "JOIN course_catalog c ON c.course_id = o.course_id "
        "WHERE r.term_registration_id = :t AND r.registration_status IN ('REGISTERED','APPROVED')"),
        {"t": obj.term_registration_id}).scalar()
    policy = db.execute(text("SELECT minimum_credits, maximum_credits FROM registration_policy WHERE programme_id = :p"),
                        {"p": obj.programme_id}).first()
    if policy is None:
        return
    lo, hi = policy
    if credits < lo or credits > hi:
        raise Conflict(f"Registered credits ({credits}) must be between {lo} and {hi} for this programme.",
                       code="credit_limits", details={"credits": float(credits), "minimum": float(lo), "maximum": float(hi)})


@before_create("evidence_document")
def _evidence(db, principal, data):
    data["approval_status_id"] = db.execute(text("SELECT approval_status_id FROM approval_status WHERE status_code = 'DRAFT'")).scalar()
    data["verification_status_id"] = db.execute(
        text("SELECT verification_status_id FROM verification_status WHERE status_code = 'PENDING'")).scalar()
