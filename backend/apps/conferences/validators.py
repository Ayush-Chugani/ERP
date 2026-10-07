"""Local metadata normalization. These checks do not verify publication claims."""

import re
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def doi(value):
    if value is None or not value.strip():
        return None
    value = value.strip()
    if value.lower().startswith(("https://", "http://")):
        parts = urlsplit(value)
        if (
            parts.netloc.lower() not in ("doi.org", "dx.doi.org")
            or parts.query
            or parts.fragment
        ):
            raise ValidationError("Use a DOI or a doi.org URL without query/fragment.")
        value = unquote(parts.path.lstrip("/"))
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE).lower()
    if (
        len(value) > 255
        or not re.fullmatch(r"10\.[0-9]{4,9}/\S+", value)
        or any(ord(c) < 33 for c in value)
    ):
        raise ValidationError("Enter a valid DOI identifier.")
    return value


def scholarly_number(value, kind):
    if value is None or not value.strip():
        return None
    value = re.sub(r"[\s-]", "", value).upper()
    pattern = r"[0-9]{7}[0-9X]" if kind == "issn" else r"(?:[0-9]{9}[0-9X]|[0-9]{13})"
    if not re.fullmatch(pattern, value):
        raise ValidationError(f"Enter a valid {kind.upper()} format.")
    # Format-only policy permits historical records without asserting registration.
    return value[:4] + "-" + value[4:] if kind == "issn" else value


def normalize(row):
    for field in row._meta.concrete_fields:
        value = getattr(row, field.attname)
        if isinstance(value, str):
            value = value.strip()
            setattr(row, field.attname, value if value or not field.null else None)
    for name in ("conference_website", "brochure_url", "proceedings_url", "source_url"):
        value = getattr(row, name, None)
        if value:
            URLValidator(schemes=["http", "https"])(value)
            if urlsplit(value).username or urlsplit(value).password:
                raise ValidationError({name: "URL credentials are not allowed."})
    if hasattr(row, "doi"):
        row.doi = doi(row.doi)
        row.isbn = scholarly_number(row.isbn, "isbn")
        row.issn = scholarly_number(row.issn, "issn")
        if (
            row.page_from
            and row.page_to
            and row.page_from.isascii()
            and row.page_to.isascii()
            and row.page_from.isdigit()
            and row.page_to.isdigit()
            and int(row.page_to) < int(row.page_from)
        ):
            raise ValidationError(
                {"page_to": "Final page must not precede first page."}
            )
        if row.award_date and not row.award_name:
            raise ValidationError(
                {"award_name": "An award date requires an award name."}
            )
        code = row.conference_contribution_type.type_code
        for name in getattr(settings, "CONFERENCES_CONTRIBUTION_REQUIREMENTS", {}).get(
            code, []
        ):
            if name not in (
                "paper_title",
                "presentation_title",
                "proceedings_title",
                "publication_type_id",
            ):
                raise ValidationError(
                    "Invalid conference contribution policy configuration."
                )
            if not getattr(row, name):
                raise ValidationError({name: "Required for this contribution type."})
    row.full_clean(
        exclude=["staff_activity"]
        if hasattr(row, "staff_activity_id") and not row.staff_activity_id
        else [],
        validate_unique=False,
        validate_constraints=False,
    )


def active_references(row):
    for field in row._meta.concrete_fields:
        if field.is_relation and getattr(row, field.attname) is not None:
            target = getattr(row, field.name)
            if hasattr(target, "is_active") and not target.is_active:
                raise ValidationError({field.name: "Select an active reference."})
