"""CSV adapter for the existing bounded, atomic import convention."""

import csv
import io
import re

from django.core.exceptions import ValidationError as DomainError
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.identity_access.audit import record

from . import services as s
from .models import StaffProfessionalMembership
from .permissions import principal

COLUMNS = [
    "employee_assignment_id",
    "academic_year_id",
    "context_date",
    *[
        f.attname
        for f in StaffProfessionalMembership._meta.concrete_fields
        if not f.primary_key
    ],
]


def import_csv(actor, data, key):
    from .api import MembershipSave

    actor = principal(actor)
    if not isinstance(data, dict) or set(data) - {"csv", "dry_run"}:
        raise ValidationError("Use csv and dry_run only.")
    content = data.get("csv")
    dry = data.get("dry_run", True)
    if (
        not isinstance(content, str)
        or len(content.encode("utf-8")) > 262144
        or not isinstance(dry, bool)
    ):
        raise ValidationError("Supply CSV up to 256KiB and a boolean dry_run.")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", key):
        raise ValidationError(
            "Supply a stable import Idempotency-Key of 1-80 safe characters."
        )
    try:
        reader = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames or []
        if (
            not headers
            or len(headers) != len(set(headers))
            or set(headers) - set(COLUMNS)
        ):
            raise ValidationError("Unknown or duplicated CSV headers.")
        rows = list(reader)
    except csv.Error as error:
        raise ValidationError("Invalid CSV.") from error
    if not 1 <= len(rows) <= 200:
        raise ValidationError("Use batches of 1-200 records.")
    errors = []
    count = 0
    with transaction.atomic():
        for number, row in enumerate(rows, 2):
            try:
                with transaction.atomic():
                    if None in row or any(v is None for v in row.values()):
                        raise ValidationError("Row has a different number of columns.")
                    context = {}
                    values = {}
                    for name, value in row.items():
                        value = value.strip()
                        if name in {
                            "employee_assignment_id",
                            "academic_year_id",
                            "context_date",
                        }:
                            if value:
                                context[name] = value
                        else:
                            if not value and name in {
                                "membership_status",
                                "is_lifetime_membership",
                                "renewal_required",
                            }:
                                continue
                            values[name] = value or None
                    serializer = MembershipSave(
                        data={"context": context, "activity": values}
                    )
                    serializer.is_valid(raise_exception=True)
                    parsed = serializer.validated_data
                    s.save_activity(
                        actor,
                        parsed["activity"],
                        context=parsed.get("context"),
                        key=f"import:{key}:{number}",
                    )
                    count += 1
            except (DomainError, APIException) as error:
                detail = (
                    getattr(error, "message_dict", None)
                    or getattr(error, "detail", None)
                    or getattr(error, "messages", ["Invalid row"])
                )
                errors.append({"row": number, "errors": detail})
        if dry or errors:
            transaction.set_rollback(True)
    record(
        actor=actor,
        module=s.MODULE,
        action="READ" if dry else "CREATE",
        details={
            "source": "membership_import",
            "rows": len(rows),
            "valid_rows": count,
            "error_count": len(errors),
            "dry_run": dry,
            "committed": not dry and not errors,
        },
    )
    return {
        "dry_run": dry,
        "rows": len(rows),
        "valid_rows": count,
        "errors": errors,
        "committed": not dry and not errors,
    }
