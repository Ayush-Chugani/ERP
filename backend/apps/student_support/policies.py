from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

ASSIGNMENT = ("ACTIVE", "COMPLETED", "CANCELLED")
SESSION = ("SCHEDULED", "COMPLETED", "CANCELLED", "FOLLOW_UP_REQUIRED")
LEVELS = ("NORMAL", "RESTRICTED", "HIGHLY_RESTRICTED")
PRIORITY = ("LOW", "NORMAL", "HIGH", "URGENT")
STATUS = ("SUBMITTED", "ASSIGNED", "UNDER_REVIEW", "RESOLVED", "REJECTED", "CLOSED")
ACTIONS = ("SUBMITTED", "ASSIGNED", "REVIEW_STARTED", "RESOLVED", "REJECTED", "CLOSED")
TRANSITIONS = {
    "SUBMITTED": {"ASSIGNED", "UNDER_REVIEW", "REJECTED"},
    "ASSIGNED": {"UNDER_REVIEW", "RESOLVED", "REJECTED"},
    "UNDER_REVIEW": {"RESOLVED", "REJECTED"},
    "RESOLVED": {"CLOSED"},
    "REJECTED": {"CLOSED"},
    "CLOSED": set(),
}
CAPABILITIES = (
    "manage_mentor_assignments",
    "conduct_counselling",
    "view_counselling_normal",
    "view_counselling_restricted",
    "view_counselling_highly_restricted",
    "change_counselling_confidentiality",
    "view_counselling_all",
    "submit_own_grievance",
    "view_own_grievance",
    "triage_grievance",
    "resolve_grievance",
    "close_grievance",
    "manage_grievance_categories",
    "view_grievance_reports",
    "view_grievance_queue",
)


def policy(institution_id, name, default):
    configured = settings.STUDENT_SUPPORT_POLICIES
    if not isinstance(configured, dict):
        raise ImproperlyConfigured(
            "Support policies must be an institution-keyed object."
        )
    values = configured.get(str(institution_id), {})
    if not isinstance(values, dict):
        raise ImproperlyConfigured("Institution support policy must be an object.")
    value = values.get(name, default)
    if type(value) is not bool:
        raise ImproperlyConfigured("Support policy values must be JSON booleans.")
    return value
