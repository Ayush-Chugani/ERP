"""Local invariants; cross-record rules belong to governed services."""

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
import unicodedata


def clean_local(obj):
    errors = {}
    for field in obj._meta.fields:
        if isinstance(field, models.GeneratedField):
            continue
        value = getattr(obj, field.attname)
        if isinstance(value, str):
            value = unicodedata.normalize("NFC", value).strip()
            if field.name in ("email", "primary_email"):
                value = value.lower()
            setattr(obj, field.attname, value or (None if field.null else ""))
    for start, end in [
        ("valid_from", "valid_to"),
        ("start_date", "end_date"),
        ("contract_start_date", "contract_end_date"),
    ]:
        a, b = getattr(obj, start, None), getattr(obj, end, None)
        if a and b and b < a:
            errors[end] = "Must be on or after the start date."
    dob = getattr(obj, "date_of_birth", None)
    if dob and dob > timezone.localdate():
        errors["date_of_birth"] = "Birth date cannot be in the future."
    if getattr(obj, "rank_number", None) is not None and obj.rank_number < 1:
        errors["rank_number"] = "Rank must be positive."
    for name in ("joining_date", "admission_date"):
        value = getattr(obj, name, None)
        if dob and value and value < dob:
            errors[name] = "Must not precede birth date."
    if getattr(obj, "photo_url", None) and not obj.photo_url.startswith("https://"):
        errors["photo_url"] = (
            "Use an HTTPS URL. Remote content is never fetched by this service."
        )
    if errors:
        raise ValidationError(errors)
