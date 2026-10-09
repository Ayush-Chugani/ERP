"""Build the resource registry: one ResourceSpec per exposed table, with module/permission mapping and overrides."""
import re

from app.resources import activity, domain_hooks, rules, workflows  # noqa: F401
from app.resources.spec import (
    BY_PATH,
    REGISTRY,
    ResourceSpec,
    build_columns,
    build_models,
    label_columns,
    search_columns,
    table_to_model,
)

# model module -> (url module slug, permission module, navigation group, public_read)
MODULES: dict[str, tuple[str, str, str, bool]] = {
    "common_reference": ("reference", "REFERENCE", "Reference data", True),
    "organization": ("organization", "INSTITUTION", "Organization", True),
    "tenancy": ("tenancy", "IAM", "Identity and access", False),
    "identity_access": ("security", "IAM", "Identity and access", False),
    "accounts": ("accounts", "IAM", "Identity and access", False),
    "academic_calendar": ("calendar", "ACADEMIC_CALENDAR", "Academic calendar", False),
    "curriculum_catalog": ("curriculum", "CURRICULUM", "Curriculum", False),
    "people_master": ("people", "STUDENT", "People", False),
    "employee_hr": ("hr", "EMPLOYEE", "People", False),
    "staff_profile": ("staff-profile", "EMPLOYEE", "Staff profile", False),
    "admission_enrolment": ("admissions", "ADMISSION", "Admissions", False),
    "term_registration": ("registration", "REGISTRATION", "Registration", False),
    "teaching_timetable": ("timetable", "TIMETABLE", "Timetable", False),
    "attendance_lesson_plan": ("attendance", "ATTENDANCE", "Attendance", False),
    "assessments_results": ("assessments", "ASSESSMENT", "Assessments and results", False),
    "feedback": ("feedback", "FEEDBACK", "Feedback", False),
    "student_support": ("support", "MENTORING", "Student support", False),
    "documents_exit": ("documents", "DOCUMENT", "Documents and exits", False),
    "communication": ("communication", "COMMUNICATION", "Communication", False),
    "evidence": ("evidence", "EVIDENCE", "Evidence", False),
    "awards": ("awards", "AWARDS", "Awards", False),
    "conferences": ("conferences", "CONFERENCES", "Conferences", False),
    "consultancy": ("consultancy", "CONSULTANCY", "Consultancy", False),
    "funded_projects": ("funded-projects", "FUNDED_PROJECTS", "Funded projects", False),
    "research_proposals": ("research-proposals", "RESEARCH_PROPOSALS", "Research proposals", False),
    "research_publications": ("research-publications", "RESEARCH_PUBLICATIONS", "Research publications", False),
    "faculty_internships": ("faculty-internships", "FACULTY_INTERNSHIPS", "Faculty internships", False),
    "professional_contributions": ("professional-contributions", "PROFESSIONAL_CONTRIBUTIONS",
                                   "Professional contributions", False),
    "professional_memberships": ("professional-memberships", "PROFESSIONAL_MEMBERSHIPS",
                                 "Professional memberships", False),
    "cocurricular": ("cocurricular", "COCURRICULAR", "Co-curricular", False),
    "extracurricular": ("extracurricular", "EXTRACURRICULAR", "Extra-curricular", False),
    "staff_activities": ("staff-activities", "STAFF_ACTIVITIES", "Staff activities", False),
}

# Tables that are never exposed through the generic API (handled by dedicated endpoints or internal only).
NOT_EXPOSED = {
    "user_account", "password_history", "person_account_link", "account_invitation", "file_object",
    "user_role_assignment", "role_permission", "user_permission_override", "role_delegation",
}
# Exposed read-only (no create/update/delete through the generic API).
READ_ONLY = {
    "login_audit", "evidence_document_audit", "consultancy_receipt", "consultancy_receipt_void",
    "research_utilization_void", "feedback_ledger", "feedback_response", "feedback_response_item",
    "feedback_response_item_choice", "student_course_result", "student_term_result", "enrolment_status_history",
    "access_action", "access_module", "access_resource", "permission", "staff_activity",
    "employee_aadhaar", "employee_pan", "employee_bank_account",   # written only through /hr/secure (encrypted)
}
# Per-table permission module overrides (default comes from the model module).
PERM_MODULE = {
    "employee": "EMPLOYEE", "employee_address": "EMPLOYEE", "employee_assignment": "EMPLOYEE",
    "employee_competency": "EMPLOYEE", "employee_qualification": "EMPLOYEE",
    "employee_previous_employment": "EMPLOYEE", "employee_aadhaar": "EMPLOYEE", "employee_pan": "EMPLOYEE",
    "employee_bank_account": "EMPLOYEE",
    "faculty_course_assignment": "TEACHING", "course_offering_section": "TEACHING",
    "timetable_session": "TIMETABLE", "grievance": "GRIEVANCE", "grievance_action": "GRIEVANCE",
    "grievance_category": "GRIEVANCE", "student_course_result": "RESULT", "student_term_result": "RESULT",
    "result_publication": "RESULT", "grade_scale": "RESULT", "grade_rule": "RESULT",
}
# Fine-grained permission resource codes already used by the migrated role design (default: the table name).
PERM_RESOURCE = {
    "award_category": "MASTER", "cocurricular_category": "MASTER", "extracurricular_category": "MASTER",
    "professional_contribution_type": "MASTER", "membership_type": "MASTER",
    "conference_event": "EVENT", "consultancy_milestone": "MILESTONE", "consultancy_team_member": "TEAM",
    "consultancy_receipt": "FINANCE", "consultancy_receipt_void": "FINANCE",
    "research_project_financial_utilization": "FINANCE", "research_utilization_void": "FINANCE",
    "evidence_document": "DOCUMENT", "evidence_tag": "TAG", "evidence_document_tag": "TAG",
    "evidence_document_version": "FILE", "evidence_document_audit": "AUDIT", "evidence_type": "CLASSIFICATION",
}
# Records people may create for themselves (students raising requests, registering for courses, …).
SELF_CREATE = {
    "grievance": set(), "certificate_request": {"purpose"}, "student_term_registration": {"class_section_id", "class_batch_id"},
    "student_course_registration": set(), "attendance_correction_request": {"reason", "evidence_reference"},
    "student_document": {"document_number", "issue_date", "expiry_date"},
}
def _published(col: str, value: str):
    return lambda q, spec: q.where(spec.col(col) == value)


def _published_event_marks(q, spec):
    from sqlalchemy import select as _select

    from app.models.assessments_results import AssessmentEvent

    return q.where(spec.col("assessment_event_id").in_(
        _select(AssessmentEvent.assessment_event_id).where(AssessmentEvent.status == "PUBLISHED")))


# Students (SELF scope) only ever see results once they have been published.
SELF_VISIBLE = {
    "student_course_result": _published("state", "PUBLISHED"), "student_term_result": _published("state", "PUBLISHED"),
    "assessment_event": _published("status", "PUBLISHED"), "student_assessment_mark": _published_event_marks,
    "timetable_revision": _published("status", "PUBLISHED"),
}
SLUG_OVERRIDES: dict[str, str] = {}
# Resources readable by every signed-in user (rows still honour scope rules where the table is organisational).
PUBLIC_READ_EXTRA = {"academic_year", "academic_term", "semester"}


# Models whose rows people maintain themselves (their own research / professional records).
SELF_SERVICE_MODULES = {
    "staff_activities", "research_publications", "awards", "conferences", "consultancy", "funded_projects",
    "research_proposals", "faculty_internships", "professional_contributions", "professional_memberships",
    "cocurricular", "extracurricular", "evidence",
}
# Explicit field whitelists for personal data that a student/employee may edit about themselves.
SELF_FIELDS = {
    "student": {"primary_phone", "photo_url"},
    "student_address": {"address_line1", "address_line2", "city", "district", "postal_code", "state_id", "country_id"},
}
PROTECTED_ON_SELF_UPDATE = re.compile(r"(status|institution_id|campus_id|department_id|programme_id|employee_id|"
                                      r"student_id|_by_id$|^version$|approved|verified)")


def _module_name(model) -> str:
    return model.__module__.rsplit(".", 1)[-1]


def build_registry() -> dict[str, ResourceSpec]:
    if REGISTRY:
        return REGISTRY
    models = table_to_model()
    for table, model in sorted(models.items()):
        mod = _module_name(model)
        if mod not in MODULES or table in NOT_EXPOSED:
            continue
        module_slug, perm_module, group, public = MODULES[mod]
        cols = build_columns(model.__table__)
        parent_model = parent_cols = None
        if table in activity.ACTIVITY_TYPES:
            parent_model = models[activity.PARENT_TABLE]
            parent_cols = activity.merge_columns(cols, build_columns(parent_model.__table__))
        pk_cols = [c for c in cols.values() if c.pk]
        if len(model.__table__.primary_key.columns) != 1 or not pk_cols:
            # composite-key association tables are exposed read-only; keyed access is by composite filters
            pk_name = next(iter(cols))
            composite = True
        else:
            pk_name, composite = pk_cols[0].name, False
        slug = SLUG_OVERRIDES.get(table, table.replace("_", "-"))
        title = re.sub(r"\s+", " ", table.replace("_", " ")).strip().capitalize()
        spec = ResourceSpec(
            table=table, model=model, slug=slug, module_slug=module_slug,
            perm_module=PERM_MODULE.get(table, perm_module), perm_resource=PERM_RESOURCE.get(table) or ("ACTIVITY" if table in activity.ACTIVITY_TYPES else table.upper()), title=title, group=group,
            pk=pk_name, columns=cols, search=search_columns(cols), label_cols=label_columns(model.__table__, cols),
            order_default=[], read_only=table in READ_ONLY or composite,
            public_read=public or table in PUBLIC_READ_EXTRA,
            soft_delete="deleted_at" in cols, versioned="version" in cols,
        )
        if parent_model is not None:
            spec.parent_model, spec.parent_cols, spec.soft_delete = parent_model, parent_cols, True
            spec.activity_type_code = activity.ACTIVITY_TYPES[table]
            cols[pk_name].readonly, cols[pk_name].required = True, False   # generated from the parent row
            spec.status_col, spec.status_lookup = "approval_status_id", ("approval_status", "approval_status_id", "status_code")
            spec.transitions = activity.transitions()
            spec.search = [n for n in ("activity_title", *spec.search) if n in cols][:8]
            spec.order_default = ["-" + spec.pk]
        spec.order_default = (["-" + spec.pk] if "created_at" in cols or not spec.label_cols else spec.label_cols[:1])
        if spec.public_read and spec.label_cols:
            spec.order_default = spec.label_cols[:1]
        spec.list_cols = _list_columns(spec)
        for n in rules.AUTO_FIELDS.get(table, ()):
            if n in cols:
                cols[n].required = False
        for (t, n) in rules.INITIAL_ENUM:
            if t == table and cols[n].choices:
                cols[n].required, cols[n].initial = False, cols[n].choices[0]
        if table in SELF_VISIBLE:
            spec.self_filter = SELF_VISIBLE[table]
        if table in SELF_CREATE:
            spec.self_create = True
            spec.self_fields = frozenset(SELF_CREATE[table])
        if mod in SELF_SERVICE_MODULES and not spec.read_only:
            spec.self_create = spec.self_delete = True
            spec.self_fields = frozenset(n for n, c in cols.items() if not c.readonly and not c.hidden
                                         and not PROTECTED_ON_SELF_UPDATE.search(n))
        elif table in SELF_FIELDS:
            spec.self_fields = frozenset(f for f in SELF_FIELDS[table] if f in cols)
        build_models(spec)
        REGISTRY[table] = spec
        BY_PATH[spec.path] = spec
    evidence = REGISTRY.get("evidence_document")
    if evidence is not None:   # evidence documents follow the same review chain as the activity they support
        evidence.status_col = "approval_status_id"
        evidence.status_lookup = ("approval_status", "approval_status_id", "status_code")
        evidence.transitions = activity.transitions()
        for n in ("approval_status_id", "verification_status_id"):
            evidence.columns[n].readonly, evidence.columns[n].required = True, False
        build_models(evidence)
    workflows.apply(REGISTRY)
    return REGISTRY


def _list_columns(spec: ResourceSpec) -> list[str]:
    """Sensible default table columns: the label, identifiers, key relations and the status."""
    cols = [c for c in spec.columns.values() if not c.hidden and c.kind not in ("json", "text")]
    skip = {"created_at", "updated_at", "created_by_id", "updated_by_id", "deleted_at", "version"}
    plain = [c.name for c in cols if not c.fk_table and not c.pk and c.name not in skip]
    codes = [n for n in plain if re.search(r"(code|number)$", n)]
    status = [n for n in plain if n.endswith("status") or n == "status"]
    fks = [c.name for c in cols if c.fk_table and c.name not in skip][:2]
    labels = [n for n in spec.label_cols if n in plain or n in spec.columns]
    out: list[str] = []
    for n in [*labels, *codes[:2], *fks, *status[:1], *plain]:
        if n not in out and n in spec.columns:
            out.append(n)
    return out[:7] or [c.name for c in cols][:6]
