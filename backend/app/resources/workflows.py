"""Workflow (status transition) definitions applied onto the resource registry.

Each transition names the RBAC action it needs (UPDATE, VERIFY, APPROVE, PUBLISH, ASSIGN …), the states it may start
from, the state it ends in, and whether remarks are mandatory. Every transition is audited and written to
``status_history``. ``self_service`` marks the few actions an owner (student / staff member) may run on their own
record with SELF-scoped permission.
"""
from app.resources.rules import registration_credit_guard
from app.resources.spec import ResourceSpec, Transition

T = Transition


def _hook(name, *args):
    """Late-bound domain hook (avoids import cycles between workflows and hooks)."""
    def run(db, principal, obj):
        from app.resources import domain_hooks

        fn = getattr(domain_hooks, name)
        (fn(*args) if args else fn)(db, principal, obj)
    return run


def _open_cycle(db, principal, obj):
    from app.api.routers.feedback import open_cycle_hook

    open_cycle_hook(db, principal, obj)


def _apply_correction(db, principal, obj):
    from app.api.routers.attendance import apply_correction

    apply_correction(db, principal, obj)


def _t(name, label, frm, to, action="UPDATE", remarks="optional", **kw):
    frm = (frm,) if isinstance(frm, str) else tuple(frm)
    return T(name, label, frm, to, action, remarks, **kw)


def _grievance(action):
    return _hook("grievance_log", action)


WORKFLOWS: dict[str, tuple[str, list[Transition]]] = {
    # ----------------------------------------------------------------------------------------- admissions
    "admission_application": ("application_status", [
        _t("submit", "Submit", "DRAFT", "SUBMITTED", "UPDATE", "none", self_service=True),
        _t("start_review", "Start review", "SUBMITTED", "UNDER_REVIEW", "VERIFY", "none",
           set_fields={"eligibility_status": "PENDING", "reviewer_id": "user"}),
        _t("mark_eligible", "Mark eligible", "UNDER_REVIEW", "ELIGIBLE", "VERIFY", "optional",
           set_fields={"eligibility_status": "ELIGIBLE"}, remarks_field="remarks"),
        _t("mark_ineligible", "Mark ineligible", "UNDER_REVIEW", "INELIGIBLE", "VERIFY", "required",
           set_fields={"eligibility_status": "INELIGIBLE"}, remarks_field="remarks", danger=True),
        _t("select", "Select", ("ELIGIBLE", "WAITLISTED"), "SELECTED", "APPROVE", "optional"),
        _t("waitlist", "Waitlist", "ELIGIBLE", "WAITLISTED", "APPROVE", "optional"),
        _t("reject", "Reject", ("ELIGIBLE", "WAITLISTED"), "REJECTED", "APPROVE", "required", danger=True),
        _t("cancel", "Cancel", ("DRAFT", "SUBMITTED", "UNDER_REVIEW", "ELIGIBLE", "WAITLISTED", "SELECTED"),
           "CANCELLED", "UPDATE", "required", danger=True, self_service=True),
        _t("reopen", "Reopen for review", ("INELIGIBLE", "REJECTED", "CANCELLED"), "UNDER_REVIEW", "APPROVE",
           "required", set_fields={"eligibility_status": "PENDING"}),
    ]),
    "student_programme_enrolment": ("enrolment_status", [
        _t("put_on_break", "Put on break", "ACTIVE", "ON_BREAK", "APPROVE", "required"),
        _t("resume", "Resume", "ON_BREAK", "ACTIVE", "APPROVE", "optional"),
        _t("withdraw", "Withdraw", ("ACTIVE", "ON_BREAK"), "WITHDRAWN", "APPROVE", "required", danger=True),
        _t("complete", "Mark completed", "ACTIVE", "COMPLETED", "APPROVE", "optional"),
        _t("terminate", "Terminate", ("ACTIVE", "ON_BREAK"), "TERMINATED", "APPROVE", "required", danger=True),
    ]),
    # ------------------------------------------------------------------------------------------- people
    "student": ("student_status", [
        _t("activate", "Activate", ("APPLICANT", "SUSPENDED"), "ACTIVE", "APPROVE", "optional"),
        _t("suspend", "Suspend", "ACTIVE", "SUSPENDED", "APPROVE", "required", danger=True),
        _t("withdraw", "Withdraw", ("ACTIVE", "SUSPENDED"), "WITHDRAWN", "APPROVE", "required", danger=True),
        _t("complete", "Mark completed", "ACTIVE", "COMPLETED", "APPROVE", "optional"),
        _t("make_alumnus", "Make alumnus", "COMPLETED", "ALUMNUS", "APPROVE", "optional"),
    ]),
    "employee": ("employment_status", [
        _t("activate", "Activate", ("DRAFT", "ON_LEAVE", "SUSPENDED"), "ACTIVE", "APPROVE", "optional"),
        _t("put_on_leave", "Put on leave", "ACTIVE", "ON_LEAVE", "APPROVE", "optional"),
        _t("suspend", "Suspend", "ACTIVE", "SUSPENDED", "APPROVE", "required", danger=True),
        _t("resign", "Record resignation", ("ACTIVE", "ON_LEAVE"), "RESIGNED", "APPROVE", "optional", danger=True),
        _t("retire", "Retire", ("ACTIVE", "ON_LEAVE"), "RETIRED", "APPROVE", "optional"),
        _t("terminate", "Terminate", ("ACTIVE", "ON_LEAVE", "SUSPENDED"), "TERMINATED", "APPROVE", "required",
           danger=True),
    ]),
    "student_document": ("verification_status", [
        _t("verify", "Verify", ("PENDING", "REJECTED"), "VERIFIED", "VERIFY", "optional"),
        _t("reject", "Reject", ("PENDING", "VERIFIED"), "REJECTED", "VERIFY", "required", danger=True),
    ]),
    "employee_aadhaar": ("verification_status", [
        _t("verify", "Verify", ("PENDING", "REJECTED"), "VERIFIED", "VERIFY", "optional"),
        _t("reject", "Reject", ("PENDING", "VERIFIED"), "REJECTED", "VERIFY", "required", danger=True)]),
    "employee_pan": ("verification_status", [
        _t("verify", "Verify", ("PENDING", "REJECTED"), "VERIFIED", "VERIFY", "optional"),
        _t("reject", "Reject", ("PENDING", "VERIFIED"), "REJECTED", "VERIFY", "required", danger=True)]),
    "employee_bank_account": ("verification_status", [
        _t("verify", "Verify", ("PENDING", "REJECTED"), "VERIFIED", "VERIFY", "optional",
           set_fields={"account_status": "ACTIVE"}),
        _t("reject", "Reject", ("PENDING", "VERIFIED"), "REJECTED", "VERIFY", "required", danger=True,
           set_fields={"account_status": "REJECTED"})]),
    # --------------------------------------------------------------------------------------- calendar etc.
    "academic_year": ("status", [
        _t("activate", "Activate", "PLANNED", "ACTIVE", "APPROVE", "none"),
        _t("close", "Close", "ACTIVE", "CLOSED", "APPROVE", "optional", danger=True)]),
    "academic_term": ("status", [
        _t("open_registration", "Open registration", "PLANNED", "REGISTRATION_OPEN", "APPROVE", "none"),
        _t("activate", "Activate", ("PLANNED", "REGISTRATION_OPEN"), "ACTIVE", "APPROVE", "none"),
        _t("close", "Close", "ACTIVE", "CLOSED", "APPROVE", "optional", danger=True)]),
    "curriculum_scheme": ("status", [
        _t("activate", "Activate", "DRAFT", "ACTIVE", "APPROVE", "none"),
        _t("retire", "Retire", "ACTIVE", "RETIRED", "APPROVE", "required", danger=True)]),
    "programme_term_offering": ("status", [
        _t("open_registration", "Open registration", "PLANNED", "REGISTRATION_OPEN", "PUBLISH", "none"),
        _t("activate", "Activate", ("PLANNED", "REGISTRATION_OPEN"), "ACTIVE", "PUBLISH", "none"),
        _t("complete", "Complete", "ACTIVE", "COMPLETED", "PUBLISH", "optional"),
        _t("cancel", "Cancel", ("PLANNED", "REGISTRATION_OPEN"), "CANCELLED", "PUBLISH", "required", danger=True)]),
    "course_offering": ("status", [
        _t("open", "Open", "PLANNED", "OPEN", "PUBLISH", "none"),
        _t("activate", "Activate", ("PLANNED", "OPEN"), "ACTIVE", "PUBLISH", "none"),
        _t("complete", "Complete", "ACTIVE", "COMPLETED", "PUBLISH", "optional"),
        _t("cancel", "Cancel", ("PLANNED", "OPEN"), "CANCELLED", "PUBLISH", "required", danger=True)]),
    "faculty_course_assignment": ("assignment_status", [
        _t("activate", "Activate", "PLANNED", "ACTIVE", "ASSIGN", "none"),
        _t("complete", "Complete", "ACTIVE", "COMPLETED", "ASSIGN", "optional"),
        _t("cancel", "Cancel", ("PLANNED", "ACTIVE"), "CANCELLED", "ASSIGN", "required", danger=True)]),
    "timetable_revision": ("status", [
        _t("submit_for_review", "Submit for review", "DRAFT", "REVIEW", "UPDATE", "none"),
        _t("approve", "Approve", "REVIEW", "APPROVED", "APPROVE", "optional"),
        _t("return_to_draft", "Return to draft", "REVIEW", "DRAFT", "APPROVE", "required"),
        _t("publish", "Publish", "APPROVED", "PUBLISHED", "PUBLISH", "optional"),
        _t("withdraw", "Withdraw", ("PUBLISHED",), "WITHDRAWN", "PUBLISH", "required", danger=True),
        _t("archive", "Archive", ("SUPERSEDED", "WITHDRAWN"), "ARCHIVED", "UPDATE", "none")]),
    # ---------------------------------------------------------------------------------- registration
    "student_term_registration": ("registration_status", [
        _t("submit", "Submit registration", "DRAFT", "REGISTERED", "UPDATE", "none", self_service=True,
           guard=registration_credit_guard),
        _t("approve", "Approve", "REGISTERED", "APPROVED", "APPROVE", "optional", guard=registration_credit_guard),
        _t("cancel", "Cancel", ("DRAFT", "REGISTERED", "APPROVED"), "CANCELLED", "UPDATE", "required",
           danger=True, self_service=True),
        _t("complete", "Mark completed", "APPROVED", "COMPLETED", "APPROVE", "none")]),
    "student_course_registration": ("registration_status", [
        _t("approve", "Approve", "REGISTERED", "APPROVED", "APPROVE", "optional"),
        _t("drop", "Drop course", ("REGISTERED", "APPROVED"), "DROPPED", "UPDATE", "required", danger=True,
           self_service=True),
        _t("withdraw", "Withdraw", ("REGISTERED", "APPROVED"), "WITHDRAWN", "APPROVE", "required", danger=True),
        _t("complete", "Mark completed", "APPROVED", "COMPLETED", "APPROVE", "none")]),
    # ------------------------------------------------------------------------------------- attendance
    "class_session": ("register_status", [
        _t("open_register", "Open register", ("UNOPENED",), "OPEN", "UPDATE", "none"),
        _t("finalize_register", "Finalize register", ("OPEN", "REOPENED"), "FINALIZED", "UPDATE", "none"),
        _t("reopen_register", "Reopen register", "FINALIZED", "REOPENED", "APPROVE", "required")]),
    "attendance_correction_request": ("request_status", [
        _t("approve", "Approve correction", "PENDING", "APPROVED", "APPROVE", "optional", after=_apply_correction),
        _t("reject", "Reject", "PENDING", "REJECTED", "APPROVE", "required", danger=True),
        _t("cancel", "Cancel request", "PENDING", "CANCELLED", "UPDATE", "optional", self_service=True)]),
    # ---------------------------------------------------------------------------------------- assessments
    "assessment_event": ("status", [
        _t("mark_conducted", "Mark conducted", "PLANNED", "CONDUCTED", "UPDATE", "none"),
        _t("publish", "Publish marks", "CONDUCTED", "PUBLISHED", "PUBLISH", "optional"),
        _t("cancel", "Cancel", ("PLANNED", "CONDUCTED"), "CANCELLED", "UPDATE", "required", danger=True)]),
    "student_course_result": ("state", [
        _t("publish", "Publish", ("CALCULATED",), "PUBLISHED", "PUBLISH", "optional", set_fields={"is_withheld": False}),
        _t("withhold", "Withhold", ("CALCULATED", "PUBLISHED"), "WITHHELD", "APPROVE", "required",
           set_fields={"is_withheld": True}, danger=True),
        _t("release", "Release for recalculation", "WITHHELD", "CALCULATED", "APPROVE", "optional",
           set_fields={"is_withheld": False})]),
    "student_term_result": ("state", [
        _t("publish", "Publish", ("CALCULATED",), "PUBLISHED", "PUBLISH", "optional", set_fields={"is_withheld": False}),
        _t("withhold", "Withhold", ("CALCULATED", "PUBLISHED"), "WITHHELD", "APPROVE", "required",
           set_fields={"is_withheld": True}, danger=True),
        _t("release", "Release for recalculation", "WITHHELD", "CALCULATED", "APPROVE", "optional",
           set_fields={"is_withheld": False})]),
    # --------------------------------------------------------------------------------------------- feedback
    "feedback_cycle": ("status", [
        _t("open", "Open for responses", "SCHEDULED", "OPEN", "PUBLISH", "none", after=_open_cycle),
        _t("close", "Close", "OPEN", "CLOSED", "PUBLISH", "optional"),
        _t("cancel", "Cancel", ("SCHEDULED", "OPEN"), "CANCELLED", "PUBLISH", "required", danger=True)]),
    "feedback_questionnaire": ("status", [
        _t("activate", "Activate", "DRAFT", "ACTIVE", "PUBLISH", "none"),
        _t("retire", "Retire", "ACTIVE", "RETIRED", "PUBLISH", "optional", danger=True)]),
    # ------------------------------------------------------------------------------------------ support
    "grievance": ("status", [
        _t("assign", "Assign", "SUBMITTED", "ASSIGNED", "ASSIGN", "optional", after=_grievance("assign")),
        _t("start_review", "Start review", "ASSIGNED", "UNDER_REVIEW", "UPDATE", "none", after=_grievance("start_review")),
        _t("resolve", "Resolve", ("ASSIGNED", "UNDER_REVIEW"), "RESOLVED", "APPROVE", "required",
           remarks_field="resolution", after=_grievance("resolve")),
        _t("reject", "Reject", ("SUBMITTED", "ASSIGNED", "UNDER_REVIEW"), "REJECTED", "APPROVE", "required",
           danger=True, remarks_field="resolution", after=_grievance("reject")),
        _t("close", "Close", ("RESOLVED", "REJECTED"), "CLOSED", "UPDATE", "optional", after=_grievance("close"))]),
    "counselling_session": ("session_status", [
        _t("complete", "Mark completed", ("SCHEDULED", "FOLLOW_UP_REQUIRED"), "COMPLETED", "UPDATE", "optional"),
        _t("follow_up", "Needs follow-up", "SCHEDULED", "FOLLOW_UP_REQUIRED", "UPDATE", "optional"),
        _t("cancel", "Cancel", ("SCHEDULED", "FOLLOW_UP_REQUIRED"), "CANCELLED", "UPDATE", "required",
           danger=True)]),
    "mentor_assignment": ("assignment_status", [
        _t("complete", "Complete", "ACTIVE", "COMPLETED", "ASSIGN", "optional"),
        _t("cancel", "Cancel", "ACTIVE", "CANCELLED", "ASSIGN", "required", danger=True)]),
    # ----------------------------------------------------------------------------------------- documents
    "certificate_request": ("request_status", [
        _t("start_review", "Start review", "SUBMITTED", "UNDER_REVIEW", "VERIFY", "none"),
        _t("approve", "Approve", "UNDER_REVIEW", "APPROVED", "APPROVE", "optional"),
        _t("reject", "Reject", ("SUBMITTED", "UNDER_REVIEW"), "REJECTED", "APPROVE", "required", danger=True),
        _t("issue", "Issue certificate", "APPROVED", "ISSUED", "PUBLISH", "optional", after=_hook("certificate_issued")),
        _t("cancel", "Cancel request", ("SUBMITTED", "UNDER_REVIEW"), "CANCELLED", "UPDATE", "optional",
           self_service=True)]),
    # ------------------------------------------------------------------------------------ communication
    "announcement": ("approval_status", [
        _t("submit", "Submit for approval", ("DRAFT", "REJECTED"), "PENDING", "UPDATE", "none"),
        _t("approve", "Approve and publish", "PENDING", "APPROVED", "APPROVE", "optional", after=_hook("announcement_approved")),
        _t("reject", "Reject", "PENDING", "REJECTED", "APPROVE", "required", danger=True),
        _t("archive", "Archive", "APPROVED", "ARCHIVED", "UPDATE", "none")]),
    # ---------------------------------------------------------------------------------------- research
    "staff_professional_membership": ("membership_status", [
        _t("suspend", "Suspend", "ACTIVE", "SUSPENDED", "UPDATE", "required"),
        _t("reactivate", "Reactivate", "SUSPENDED", "ACTIVE", "UPDATE", "none"),
        _t("expire", "Mark expired", "ACTIVE", "EXPIRED", "UPDATE", "none"),
        _t("cancel", "Cancel", ("ACTIVE", "SUSPENDED"), "CANCELLED", "UPDATE", "required", danger=True)]),
    "consultancy_milestone": ("status", [
        _t("complete", "Mark completed", "PLANNED", "COMPLETED", "UPDATE", "optional"),
        _t("accept", "Client accepted", "COMPLETED", "ACCEPTED", "UPDATE", "optional"),
        _t("cancel", "Cancel", "PLANNED", "CANCELLED", "UPDATE", "required", danger=True)]),
}


def apply(registry: dict[str, ResourceSpec]) -> None:
    for table, (status_col, transitions) in WORKFLOWS.items():
        spec = registry.get(table)
        if spec is None or status_col not in spec.columns or spec.transitions:
            continue
        spec.status_col = status_col
        spec.transitions = {t.name: t for t in transitions}
