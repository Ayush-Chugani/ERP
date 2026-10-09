"""Sign-in portals: each audience signs in through its own entrance and can only enter the one its roles belong to."""

PORTALS: dict[str, dict] = {
    "student": {"label": "Student", "roles": {"STUDENT", "ALUMNI", "APPLICANT", "PARENT_GUARDIAN"}},
    "faculty": {"label": "Faculty", "roles": {
        "FACULTY", "LAB_INSTRUCTOR", "FACULTY_ADVISOR", "MENTOR", "EVALUATOR", "COURSE_COORDINATOR",
        "TIMETABLE_COORDINATOR", "PROGRAMME_COORDINATOR", "SEMESTER_COORDINATOR"}},
    "leadership": {"label": "Department & campus heads", "roles": {
        "HEAD_DEPARTMENT", "DEAN_ACADEMICS", "CAMPUS_DIRECTOR", "VICE_CHANCELLOR"}},
    "office": {"label": "Registrar & admissions", "roles": {
        "REGISTRAR", "STUDENT_SECTION_OFFICER", "ADMISSION_OFFICER", "DOCUMENT_VERIFIER"}},
    "exam": {"label": "Examination cell", "roles": {
        "CONTROLLER_EXAMINATIONS", "EXAMINATION_OFFICER", "RESULT_APPROVER"}},
    "support": {"label": "Support & finance", "roles": {
        "GRIEVANCE_OFFICER", "FINANCE_OFFICER", "INTERNAL_AUDITOR", "EXTERNAL_AUDITOR"}},
    "organisation": {"label": "Organisation administrator", "roles": {"INSTITUTION_ADMIN"}},
    "admin": {"label": "Administrator", "roles": {"SUPER_ADMIN", "SYSTEM_ADMIN", "SECURITY_ADMIN", "DATABASE_ADMIN"}},
}


def portals_of(role_codes: set[str], is_superuser: bool) -> list[str]:
    """Portal keys a person may use, given their active roles (super administrators belong to the admin portal)."""
    keys = [k for k, p in PORTALS.items() if p["roles"] & role_codes]
    if is_superuser and "admin" not in keys:
        keys.append("admin")
    return keys
