"""Single source of field validation; no unapproved type requirements by default."""

from django.conf import settings
from django.core.exceptions import ValidationError

COUNTS = ("number_of_reviews", "number_of_candidates")
TEXT = ("contribution_details", "outcome_details")
CONTEXT = (
    "organization",
    "journal",
    "conference_event",
    "programme",
    "course",
    "student",
)
POLICY_FIELDS = (
    *[name + "_id" for name in CONTEXT],
    "title_topic",
    "appointment_reference_number",
    "contribution_date",
    "start_date",
    "end_date",
    *COUNTS,
    *TEXT,
)


def requirements(code):
    fields = settings.PROFESSIONAL_CONTRIBUTIONS_TYPE_RULES.get(code, [])
    if not isinstance(fields, (list, tuple)) or any(
        f not in POLICY_FIELDS for f in fields
    ):
        raise ValidationError(
            "The contribution type policy needs administrator review."
        )
    return list(fields)


def validate_contribution(row):
    errors = {}
    if row.start_date and row.end_date and row.end_date < row.start_date:
        errors["end_date"] = "End date cannot precede start date."
    for name in COUNTS:
        value = getattr(row, name)
        if value is not None and (type(value) is not int or not 0 <= value <= 65535):
            errors[name] = "Use a whole number from 0 to 65,535."
    for name in TEXT:
        value = getattr(row, name)
        if value and len(value.encode("utf-8")) > 65535:
            errors[name] = "Text exceeds the 65,535-byte storage limit."
    if row.professional_contribution_type_id:
        try:
            kind = row.professional_contribution_type
        except row._meta.get_field(
            "professional_contribution_type"
        ).remote_field.model.DoesNotExist:
            errors["professional_contribution_type_id"] = (
                "Select an active contribution type."
            )
        else:
            if not kind.is_active:
                errors["professional_contribution_type_id"] = (
                    "Select an active contribution type."
                )
            for name in requirements(kind.contribution_code):
                if getattr(row, name) in (None, ""):
                    errors[name] = "Required by the selected contribution type policy."
    if errors:
        raise ValidationError(errors)
