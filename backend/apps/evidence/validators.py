from django.core.exceptions import ValidationError


def validate_document(row):
    errors = {}
    if (
        row.document_issue_date
        and row.expiry_date
        and row.expiry_date < row.document_issue_date
    ):
        errors["expiry_date"] = "Expiry cannot precede issue date."
    if row.description and len(row.description.encode("utf-8")) > 65535:
        errors["description"] = "Description exceeds the 65,535-byte storage limit."
    for user, stamp in (
        ("verified_by_user_id", "verified_at"),
        ("approved_by_user_id", "approved_at"),
        ("deleted_by_user_id", "deleted_at"),
    ):
        if bool(getattr(row, user)) != bool(getattr(row, stamp)):
            errors[stamp] = "Actor and timestamp must be recorded together."
    if errors:
        raise ValidationError(errors)
