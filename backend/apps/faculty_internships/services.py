import hashlib
import json
import re
from datetime import date
from functools import wraps

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.identity_access.audit import record
from apps.identity_access.models import ActivityAudit
from apps.people_master.models import EmployeeAssignment
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_activities.workflow import TRANSITIONS, status, transition
from apps.staff_profile.models import ActivityType, ApprovalStatus, VerificationStatus

from .models import FacultyInternship
from .permissions import principal, require

MODULE = "FACULTY_INTERNSHIPS"
TYPE_CODE = "FACULTY_INTERNSHIP"
EDITABLE = {"DRAFT", "RETURNED"}
CATEGORIES = (
    "OFFER_LETTER",
    "COMPLETION_CERTIFICATE",
    "ORGANIZATION_LETTER",
    "WORK_REPORT",
    "PHOTOGRAPH",
    "MOU",
    "OTHER",
)


class Conflict(APIException):
    status_code = 409
    default_detail = "The request conflicts with a newer edit or an earlier retry. Refresh the record."


def command(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            with transaction.atomic():
                return fn(*args, **kwargs)
        except ObjectDoesNotExist:
            raise NotFound() from None
        except IntegrityError:
            raise Conflict() from None
        except OperationalError as error:
            if error.args and error.args[0] in (1205, 1213):
                raise Conflict(
                    "Scheduling conflict; retry using the same request key."
                ) from None
            raise

    return run


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def version(pk):
    return digest(
        [
            ActivityAudit.objects.filter(
                module_code=MODULE, entity_name="staff_activity", entity_id=str(pk)
            )
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first(),
            StaffActivity.objects.values().get(pk=pk),
            FacultyInternship.objects.values().get(pk=pk),
            list(
                ActivityAttachment.objects.filter(staff_activity_id=pk)
                .order_by("pk")
                .values()
            ),
        ]
    )


def locked(actor, pk, action):
    principal(actor)
    parent = StaffActivity.objects.select_for_update().get(
        pk=pk, deleted_at__isnull=True
    )
    actor = require(actor, "ACTIVITY", action, parent)
    if (
        parent.activity_type.activity_type_code != TYPE_CODE
        or parent.activity_type.activity_group != "INTERNSHIP"
    ):
        raise ValidationError("Activity has an incompatible specialization.")
    from apps.staff_activities.specialization import ensure_exclusive

    ensure_exclusive(parent, FacultyInternship)
    FacultyInternship.objects.get(pk=pk)
    return actor, parent


def editable(parent):
    if (
        parent.approval_status.status_code not in EDITABLE
        or parent.approval_status.is_terminal
    ):
        raise ValidationError("Only draft or returned records can be edited.")


def check_version(parent, expected):
    if not expected or version(parent.pk) != expected:
        raise Conflict()


def retry(actor, key, operation, payload, execute, authorize):
    actor = principal(actor)
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", key):
        raise ValidationError("Supply an Idempotency-Key of 1?100 safe characters.")
    # Serialize this actor's commands, including the first receipt creation.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    fingerprint = digest(payload)
    receipt = ActivityCommandReceipt.objects.filter(actor=actor, key=key).first()
    if receipt:
        if receipt.operation != operation or receipt.digest != fingerprint:
            raise Conflict()
        actor, parent = locked(actor, receipt.staff_activity_id, authorize)
        require(actor, "ACTIVITY", "READ", parent)
        return FacultyInternship.objects.get(pk=parent.pk)
    row = execute()
    ActivityCommandReceipt.objects.create(
        actor=actor,
        key=key,
        operation=operation,
        digest=fingerprint,
        staff_activity_id=row.pk,
    )
    return row


def normalize(row):
    for field in row._meta.concrete_fields:
        value = getattr(row, field.attname)
        if isinstance(value, str):
            setattr(row, field.attname, value.strip())
    if not row.internship_title:
        raise ValidationError({"internship_title": "A title is required."})
    if row.mentor_email:
        try:
            validate_email(row.mentor_email)
        except ValidationError:
            raise ValidationError(
                {"mentor_email": "Enter a valid email address."}
            ) from None
    row.currency_code = row.currency_code.upper()
    if not re.fullmatch(r"[A-Z]{3}", row.currency_code):
        raise ValidationError({"currency_code": "Use a three-letter currency code."})
    if row.stipend_incentive_amount is not None and row.stipend_incentive_amount < 0:
        raise ValidationError(
            {"stipend_incentive_amount": "Amount cannot be negative."}
        )
    if row.stipend_incentive_type == "NONE":
        row.stipend_incentive_amount = None
    row.full_clean(
        exclude=["staff_activity"], validate_unique=False, validate_constraints=False
    )
    if not row.organization.is_active or (
        row.industry_sector_id and not row.industry_sector.is_active
    ):
        raise ValidationError("Select active organization and sector references.")


def apply(row, values):
    allowed = {f.attname for f in row._meta.concrete_fields if not f.primary_key}
    if set(values) - allowed:
        raise ValidationError("Unknown or protected internship field.")
    for key, value in values.items():
        setattr(row, key, value)


def dates(context):
    try:
        start = context["start_date"]
        end = context["end_date"]
        start = date.fromisoformat(start) if isinstance(start, str) else start
        end = date.fromisoformat(end) if isinstance(end, str) else end
        if not isinstance(start, date) or not isinstance(end, date) or end < start:
            raise ValueError()
        return start, end
    except (KeyError, TypeError, ValueError):
        raise ValidationError(
            {"end_date": "Supply valid internship dates, with end on or after start."}
        ) from None


@command
def save_activity(
    actor, values, *, context=None, activity_id=None, expected_version=None, key=None
):
    actor = principal(actor)
    context = context or {}
    if activity_id:
        actor, parent = locked(actor, activity_id, "UPDATE")
        require(actor, "ACTIVITY", "READ", parent)
        check_version(parent, expected_version)
        editable(parent)
        if context:
            raise ValidationError(
                "Ownership and internship dates cannot be replaced after creation; withdraw and recreate for context corrections."
            )
        row = FacultyInternship.objects.get(pk=activity_id)
        apply(row, values)
        normalize(row)
        parent.activity_title = row.internship_title
        parent.updated_by_user = actor
        parent.save()
        row.save()
        record(
            actor=actor,
            module=MODULE,
            action="UPDATE",
            entity=parent,
            details={"fields": sorted(values)},
        )
        return row
    if set(context) - {
        "employee_assignment_id",
        "academic_year_id",
        "start_date",
        "end_date",
    }:
        raise ValidationError("Unknown or protected parent context.")

    def create():
        start, end = dates(context)
        assignment = (
            EmployeeAssignment.objects.select_for_update()
            .select_related("employee", "campus")
            .get(pk=context.get("employee_assignment_id"))
        )
        if (
            assignment.employee.institution_id != assignment.campus.institution_id
            or assignment.start_date > start
            or (assignment.end_date and assignment.end_date < end)
        ):
            raise ValidationError(
                "Select an employee assignment valid for the full internship period."
            )
        kind = ActivityType.objects.filter(
            activity_type_code=TYPE_CODE, activity_group="INTERNSHIP", is_active=True
        ).first()
        if kind is None:
            raise ValidationError(
                "Configure the active FACULTY_INTERNSHIP activity type before creating records."
            )
        parent = StaffActivity(
            employee=assignment.employee,
            institution_id=assignment.employee.institution_id,
            campus_id=assignment.campus_id,
            department_id=assignment.department_id,
            activity_type=kind,
            academic_year_id=context.get("academic_year_id"),
            start_date=start,
            end_date=end,
            approval_status=status(ApprovalStatus, "DRAFT"),
            verification_status=status(VerificationStatus, "PENDING"),
            created_by_user=actor,
            updated_by_user=actor,
        )
        require(actor, "ACTIVITY", "CREATE", parent)
        require(actor, "ACTIVITY", "READ", parent)
        row = FacultyInternship(staff_activity=parent)
        apply(row, values)
        normalize(row)
        parent.activity_title = row.internship_title
        parent.full_clean(validate_unique=False, validate_constraints=False)
        parent.save()
        row.staff_activity = parent
        row.save()
        record(
            actor=actor,
            module=MODULE,
            action="CREATE",
            entity=parent,
            details={"fields": sorted(values)},
        )
        return row

    return retry(
        actor,
        key,
        "internship.create",
        {"context": context, "activity": values},
        create,
        "CREATE",
    )


@command
def workflow(actor, pk, action, remarks, expected_version, key):
    if action not in TRANSITIONS:
        raise ValidationError("Unsupported workflow action.")
    permission = TRANSITIONS[action][2]

    def execute():
        fresh, parent = locked(actor, pk, permission)
        require(fresh, "ACTIVITY", "READ", parent)
        check_version(parent, expected_version)
        transition(
            actor=fresh,
            parent=parent,
            command=action,
            remarks=remarks,
            authorize=require,
            module=MODULE,
        )
        return FacultyInternship.objects.get(pk=pk)

    return retry(
        actor,
        key,
        "internship." + action,
        {"pk": str(pk), "remarks": remarks, "version": expected_version},
        execute,
        permission,
    )


@command
def archive(actor, pk, expected_version):
    actor, parent = locked(actor, pk, "DELETE")
    check_version(parent, expected_version)
    if parent.approval_status.status_code not in {
        "DRAFT",
        "RETURNED",
        "WITHDRAWN",
        "REJECTED",
    }:
        raise ValidationError("Withdraw an eligible record before archiving.")
    parent.deleted_at = timezone.now()
    parent.deleted_by_user = actor
    parent.updated_by_user = actor
    parent.save()
    record(actor=actor, module=MODULE, action="DELETE", entity=parent)


def upload_attachment(
    *, actor, pk, expected_version, upload, title, category, replaces=None
):
    from apps.documents_exit.sharing import upload_shared

    def authorize(fresh):
        fresh, parent = locked(fresh, pk, "UPDATE")
        require(fresh, "ACTIVITY", "READ", parent)
        editable(parent)
        check_version(parent, expected_version)
        if (
            category not in CATEGORIES
            or not isinstance(title, str)
            or not 1 <= len(title.strip()) <= 200
        ):
            raise ValidationError(
                "Select an evidence category and title of at most 200 characters."
            )
        if replaces:
            ActivityAttachment.objects.get(
                pk=replaces, staff_activity=parent, replacement__isnull=True
            )
        return parent

    def attach(fresh, parent, file):
        link = ActivityAttachment.objects.create(
            staff_activity=parent,
            file_object=file,
            title=title.strip(),
            category=category,
            replaces_id=replaces,
        )
        record(
            actor=fresh,
            module=MODULE,
            action="UPDATE",
            entity=parent,
            details={"attachment_id": link.pk, "replaces_id": replaces},
        )
        return link

    # Evidence is always RESTRICTED and subject to M13 file-level permissions.
    return upload_shared(
        actor=actor,
        upload=upload,
        level="RESTRICTED",
        authorize=authorize,
        attach=attach,
    )


def download_attachment(*, actor, pk, attachment_id):
    from apps.documents_exit.sharing import download_shared

    def authorize(fresh):
        _, parent = locked(fresh, pk, "READ")
        ActivityAttachment.objects.get(pk=attachment_id, staff_activity=parent)
        return parent

    # Authorization happens before exposing a file identifier to the storage API.
    principal(actor)
    require(
        actor,
        "ACTIVITY",
        "READ",
        StaffActivity.objects.get(pk=pk, deleted_at__isnull=True),
    )
    link = ActivityAttachment.objects.get(pk=attachment_id, staff_activity_id=pk)
    return download_shared(
        actor=actor, file_id=link.file_object_id, authorize=authorize
    )
