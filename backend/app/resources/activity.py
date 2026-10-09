"""Staff activities: subtype tables (awards, memberships, projects, …) share one parent row (``staff_activity``) that
carries ownership, organisation and the approval workflow. They are exposed as one record per activity."""
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Invalid
from app.rbac.engine import Principal
from app.resources.spec import ColumnSpec, ResourceSpec, Transition

PARENT_TABLE = "staff_activity"
ACTIVITY_TYPES = {
    "staff_award": "AWARD_RECOGNITION",
    "cocurricular_activity": "CO_CURRICULAR",
    "consultancy_project": "CONSULTANCY_PROJECT",
    "extracurricular_activity": "EXTRA_CURRICULAR",
    "faculty_internship": "FACULTY_INTERNSHIP",
    "funded_research_project": "FUNDED_RESEARCH_PROJECT",
    "staff_professional_contribution": "ACADEMIC_PROFESSIONAL_CONTRIBUTION",
    "staff_professional_membership": "PROFESSIONAL_MEMBERSHIP",
    "research_proposal": "RESEARCH_PROPOSAL",
    "conference_activity": "CONFERENCE_ACTIVITY",
    "journal_publication": "JOURNAL_PUBLICATION",
}
# Parent columns that callers may read and (when drafting) write.
PARENT_INPUT = ("employee_id", "academic_year_id", "institution_id", "campus_id", "department_id",
                "participation_level_id", "primary_role_type_id", "activity_title", "start_date", "end_date",
                "description", "outcomes", "remarks")
PARENT_OUTPUT_ONLY = ("activity_type_id", "verification_status_id", "approval_status_id", "verified_by_user_id",
                      "verified_at", "verification_remarks", "approved_by_user_id", "approved_at", "approval_remarks",
                      "rejection_reason", "created_at", "updated_at")


def merge_columns(cols: dict[str, ColumnSpec], parent_cols: dict[str, ColumnSpec]) -> frozenset[str]:
    """Add the parent's columns to the subtype's column map; returns the names that now come from the parent."""
    added = set()
    for name in (*PARENT_INPUT, *PARENT_OUTPUT_ONLY):
        pc = parent_cols.get(name)
        if pc is None or name in cols:
            continue
        merged = ColumnSpec(**{**pc.__dict__})
        if name in PARENT_OUTPUT_ONLY:
            merged.readonly, merged.required = True, False
        elif name in ("employee_id", "institution_id", "campus_id", "department_id", "academic_year_id",
                      "participation_level_id", "primary_role_type_id"):
            merged.required = False            # filled from the caller / their assignment when omitted
        cols[name] = merged
        added.add(name)
    return frozenset(added | {"deleted_at", "deleted_by_user_id", "created_by_user_id",
                                  "updated_by_user_id"})


def prepare_activity_create(db: Session, spec: ResourceSpec, principal: Principal, data: dict) -> dict:
    """Fill ownership, organisation and initial workflow state for a new activity."""
    type_id = db.execute(text("SELECT activity_type_id FROM activity_type WHERE activity_type_code = :c"),
                         {"c": spec.activity_type_code}).scalar()
    if type_id is None:
        raise Invalid(f"Activity type {spec.activity_type_code} is not configured.")
    data["activity_type_id"] = type_id
    data["approval_status_id"] = db.execute(
        text("SELECT approval_status_id FROM approval_status WHERE status_code = 'DRAFT'")).scalar()
    data["verification_status_id"] = db.execute(
        text("SELECT verification_status_id FROM verification_status WHERE status_code = 'PENDING'")).scalar()
    data["created_by_user_id"] = data["updated_by_user_id"] = principal.user_id
    employee_id = data.get("employee_id")
    if employee_id is None:
        if len(principal.employee_ids) != 1:
            raise Invalid("Choose the staff member this record belongs to.", details={"employee_id": ["Required."]})
        employee_id = data["employee_id"] = next(iter(principal.employee_ids))
    if data.get("institution_id") is None or data.get("campus_id") is None:
        row = db.execute(text(
            "SELECT d.campus_id, d.department_id, c.institution_id FROM employee_assignment d "
            "JOIN campus c ON c.campus_id = d.campus_id WHERE d.employee_id = :e AND d.end_date IS NULL "
            "ORDER BY d.is_primary DESC, d.start_date DESC LIMIT 1"), {"e": employee_id}).first()
        if row is None:
            raise Invalid("The staff member has no current assignment; set the organisation explicitly.")
        data.setdefault("campus_id", row[0])
        data.setdefault("department_id", row[1])
        data.setdefault("institution_id", row[2])
        for k, v in zip(("campus_id", "department_id", "institution_id"), row, strict=True):
            if data.get(k) is None:
                data[k] = v
    if "department_id" in spec.columns and spec.columns["department_id"].required and not data.get("department_id"):
        raise Invalid("A department is required.", details={"department_id": ["Required."]})
    return data


def _owner(db: Session, obj: Any) -> int | None:
    owner = getattr(obj, "employee_id", None)
    if owner is None and getattr(obj, "staff_activity_id", None) is not None:   # e.g. evidence documents
        owner = db.execute(text("SELECT employee_id FROM staff_activity WHERE staff_activity_id = :a"),
                           {"a": obj.staff_activity_id}).scalar()
    return owner


def _not_own_record(db: Session, principal: Principal, obj: Any) -> None:
    if not principal.is_superuser and _owner(db, obj) in principal.employee_ids:
        raise Forbidden("You cannot review or approve your own record.")


def _mark_verification(code: str):
    def after(db: Session, principal: Principal, obj: Any) -> None:
        vid = db.execute(text("SELECT verification_status_id FROM verification_status WHERE status_code = :c"),
                         {"c": code}).scalar()
        obj.verification_status_id = vid
    return after


def transitions() -> dict[str, Transition]:
    t = Transition
    return {x.name: x for x in (
        t("submit", "Submit for review", ("DRAFT", "RETURNED"), "SUBMITTED", "UPDATE", "none", self_service=True),
        t("withdraw", "Withdraw", ("DRAFT", "SUBMITTED", "RETURNED"), "WITHDRAWN", "UPDATE", "optional",
          self_service=True, danger=True),
        t("review", "Start review", ("SUBMITTED",), "UNDER_REVIEW", "VERIFY", "none", guard=_not_own_record),
        t("return", "Return for changes", ("SUBMITTED", "UNDER_REVIEW"), "RETURNED", "VERIFY", "required",
          remarks_field="approval_remarks", guard=_not_own_record),
        t("verify", "Verify", ("SUBMITTED", "UNDER_REVIEW"), "VERIFIED", "VERIFY", "optional",
          set_fields={"verified_by_user_id": "user", "verified_at": "now"}, remarks_field="verification_remarks",
          guard=_not_own_record, after=_mark_verification("VERIFIED")),
        t("approve", "Approve", ("VERIFIED",), "APPROVED", "APPROVE", "optional",
          set_fields={"approved_by_user_id": "user", "approved_at": "now"}, remarks_field="approval_remarks",
          guard=_not_own_record),
        t("reject", "Reject", ("SUBMITTED", "UNDER_REVIEW", "VERIFIED"), "REJECTED", "APPROVE", "required",
          remarks_field="rejection_reason", danger=True, guard=_not_own_record,
          after=_mark_verification("REJECTED")),
    )}
