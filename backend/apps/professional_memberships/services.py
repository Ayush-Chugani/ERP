import hashlib
import json
import re
from datetime import date
from functools import wraps

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
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
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    VerificationStatus,
)

from .events import committed
from .models import MembershipStatusHistory, StaffProfessionalMembership
from .permissions import principal, require

MODULE = "PROFESSIONAL_MEMBERSHIPS"
TYPE_CODE = "PROFESSIONAL_MEMBERSHIP"
EDITABLE = {"DRAFT", "RETURNED"}
CATEGORIES = (
    "CERTIFICATE",
    "MEMBERSHIP",
    "MEMBERSHIP_LETTER",
    "APPROVED_EVIDENCE",
    "MEMBERSHIP_CARD",
    "APPROVED_PHOTO",
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
            StaffProfessionalMembership.objects.values().get(pk=pk),
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
        or parent.activity_type.activity_group != "MEMBERSHIP"
    ):
        raise ValidationError("Activity has an incompatible specialization.")
    from apps.staff_activities.specialization import ensure_exclusive

    ensure_exclusive(parent, StaffProfessionalMembership)
    StaffProfessionalMembership.objects.get(pk=pk)
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
        raise ValidationError("Supply an Idempotency-Key of 1-100 safe characters.")
    # Serialize this actor's commands, including the first receipt creation.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    fingerprint = digest(payload)
    receipt = ActivityCommandReceipt.objects.filter(actor=actor, key=key).first()
    if receipt:
        if receipt.operation != operation or receipt.digest != fingerprint:
            raise Conflict()
        actor, parent = locked(actor, receipt.staff_activity_id, authorize)
        require(actor, "ACTIVITY", "READ", parent)
        return StaffProfessionalMembership.objects.get(pk=parent.pk)
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
    if isinstance(row.membership_number, str):
        row.membership_number = row.membership_number.strip() or None
    row.full_clean(
        exclude=["staff_activity"], validate_unique=False, validate_constraints=False
    )
    if (
        row.membership_start_date
        and row.membership_expiry_date
        and row.membership_expiry_date < row.membership_start_date
    ):
        raise ValidationError(
            {"membership_expiry_date": "Expiry cannot precede start date."}
        )
    if row.is_lifetime_membership:
        if row.membership_expiry_date is not None or row.renewal_required:
            raise ValidationError(
                {
                    "is_lifetime_membership": "Lifetime membership requires no expiry and no renewal."
                }
            )
        if row.membership_status in {"SUSPENDED", "CANCELLED"}:
            raise ValidationError(
                {
                    "membership_status": "Administrative states cannot be converted implicitly."
                }
            )
        row.membership_status = "LIFETIME"
    elif row.membership_status == "LIFETIME":
        raise ValidationError(
            {"is_lifetime_membership": "Lifetime status requires the lifetime flag."}
        )
    for name in ("organization", "membership_type", "role_type", "participation_level"):
        if getattr(row, name + "_id") and not getattr(row, name).is_active:
            raise ValidationError({name + "_id": "Select an active reference."})
    if (
        row.membership_number
        and StaffProfessionalMembership.objects.filter(
            organization_id=row.organization_id, membership_number=row.membership_number
        )
        .exclude(pk=row.pk)
        .exists()
    ):
        raise ValidationError(
            {
                "membership_number": "This organization already has that membership number."
            }
        )
    if row.staff_activity.employee.employment_status != "ACTIVE":
        raise ValidationError("Select an active employee.")


def title(row):
    return (row.organization.organization_name + " / " + row.membership_type.type_name)[
        :500
    ]


def lifecycle_values(row):
    return {
        name: str(getattr(row, name)) if getattr(row, name) is not None else None
        for name in (
            "organization_id",
            "membership_type_id",
            "role_type_id",
            "participation_level_id",
            "membership_status",
            "membership_start_date",
            "membership_expiry_date",
            "is_lifetime_membership",
            "renewal_required",
        )
    }


def renewal_info(row, as_of=None):
    from django.conf import settings

    today = as_of or timezone.localdate()
    days = (
        (row.membership_expiry_date - today).days
        if row.membership_expiry_date
        else None
    )
    return {
        "days_to_expiry": days,
        "tenure_days": max(0, (today - row.membership_start_date).days)
        if row.membership_start_date
        else None,
        "renewal_due": bool(
            row.membership_status == "ACTIVE"
            and not row.is_lifetime_membership
            and row.renewal_required
            and days is not None
            and 0 <= days <= max(0, settings.MEMBERSHIPS_RENEWAL_WINDOW_DAYS)
        ),
    }


def apply(row, values):
    allowed = {f.attname for f in row._meta.concrete_fields if not f.primary_key}
    if set(values) - allowed:
        raise ValidationError("Unknown or protected activity field.")
    for key, value in values.items():
        setattr(row, key, value)


def dates(context):
    try:
        start = context["context_date"]
        end = start
        start = date.fromisoformat(start) if isinstance(start, str) else start
        end = date.fromisoformat(end) if isinstance(end, str) else end
        if not isinstance(start, date) or not isinstance(end, date) or end < start:
            raise ValueError()
        return start, end
    except (KeyError, TypeError, ValueError):
        raise ValidationError(
            {"context_date": "Supply the date used to select the employee assignment."}
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
                "Employee assignment context cannot be changed through this endpoint; request an audited administrative correction."
            )
        row = StaffProfessionalMembership.objects.get(pk=activity_id)
        before = lifecycle_values(row)
        for protected in ("membership_status", "is_lifetime_membership"):
            if protected in values and values[protected] != getattr(row, protected):
                raise ValidationError(
                    {
                        protected: "Use an authorized lifecycle action to change this field."
                    }
                )
        apply(row, values)
        normalize(row)
        parent.activity_title = title(row)
        parent.updated_by_user = actor
        parent.save()
        row.save()
        record(
            actor=actor,
            module=MODULE,
            action="UPDATE",
            entity=parent,
            details={
                "fields": sorted(values),
                "source": "service",
                "lifecycle_before": before,
                "lifecycle_after": lifecycle_values(row),
            },
        )
        return row
    if set(context) - {
        "employee_assignment_id",
        "academic_year_id",
        "context_date",
    }:
        raise ValidationError("Unknown or protected parent context.")

    def create():
        start, end = dates(
            {"context_date": values.get("membership_start_date")} | context
        )
        assignment = (
            EmployeeAssignment.objects.select_for_update()
            .select_related("employee", "campus", "department")
            .get(pk=context.get("employee_assignment_id"))
        )
        if (
            assignment.employee.institution_id != assignment.campus.institution_id
            or not assignment.department_id
            or assignment.department.campus_id != assignment.campus_id
            or assignment.employee.employment_status != "ACTIVE"
            or assignment.start_date > start
            or (assignment.end_date and assignment.end_date < end)
        ):
            raise ValidationError(
                "Select an employee assignment valid for the activity date."
            )
        kind = ActivityType.objects.filter(
            activity_type_code=TYPE_CODE,
            activity_group="MEMBERSHIP",
            is_active=True,
        ).first()
        if kind is None:
            raise ValidationError(
                "Configure the active PROFESSIONAL_MEMBERSHIP activity type before creating records."
            )
        parent = StaffActivity(
            employee=assignment.employee,
            institution_id=assignment.employee.institution_id,
            campus_id=assignment.campus_id,
            department_id=assignment.department_id,
            activity_type=kind,
            academic_year_id=context.get("academic_year_id"),
            start_date=start,
            end_date=None,
            approval_status=status(ApprovalStatus, "DRAFT"),
            verification_status=status(VerificationStatus, "PENDING"),
            created_by_user=actor,
            updated_by_user=actor,
        )
        require(actor, "ACTIVITY", "CREATE", parent)
        require(actor, "ACTIVITY", "READ", parent)
        row = StaffProfessionalMembership(
            staff_activity=parent,
        )
        apply(row, values)
        normalize(row)
        if row.membership_status in {"SUSPENDED", "CANCELLED", "EXPIRED"}:
            require(actor, "ACTIVITY", "VERIFY", parent)
        parent.activity_title = title(row)
        parent.full_clean(validate_unique=False, validate_constraints=False)
        parent.save()
        row.staff_activity = parent
        row.save()
        committed(
            MembershipStatusHistory.objects.create(
                activity=row,
                to_status=parent.approval_status,
                changed_by=actor,
                remarks="Draft created",
            )
        )
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
        "activity.create",
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
        row = StaffProfessionalMembership.objects.select_for_update().get(pk=pk)
        if action == "submit":
            normalize(row)
        before = parent.approval_status
        transition(
            actor=fresh,
            parent=parent,
            command=action,
            remarks=remarks,
            authorize=require,
            module=MODULE,
        )
        committed(
            MembershipStatusHistory.objects.create(
                activity=row,
                from_status=before,
                to_status=parent.approval_status,
                changed_by=fresh,
                remarks=remarks.strip(),
            )
        )
        return row

    return retry(
        actor,
        key,
        "activity." + action,
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


def create_activity(actor, values, *, context, key):
    return save_activity(actor, values, context=context, key=key)


def update_activity(actor, activity_id, values, *, expected_version):
    return save_activity(
        actor, values, activity_id=activity_id, expected_version=expected_version
    )


change_status = workflow


LIFECYCLE = {
    "renew": ({"ACTIVE", "EXPIRED"}, "ACTIVE"),
    "suspend": ({"ACTIVE", "EXPIRED"}, "SUSPENDED"),
    "cancel": ({"ACTIVE", "EXPIRED", "SUSPENDED"}, "CANCELLED"),
    "reactivate": ({"SUSPENDED", "EXPIRED"}, "ACTIVE"),
    "mark-lifetime": ({"ACTIVE", "EXPIRED"}, "LIFETIME"),
}


@command
def membership_action(
    actor, pk, action, remarks, expected_version, key, new_expiry_date=None
):
    if action not in LIFECYCLE:
        raise ValidationError("Unsupported membership action.")
    if not isinstance(remarks, str) or not 1 <= len(remarks.strip()) <= 1000:
        raise ValidationError(
            {"remarks": "Supply a reason of at most 1000 characters."}
        )

    def execute():
        fresh, parent = locked(actor, pk, "VERIFY")
        require(fresh, "ACTIVITY", "READ", parent)
        check_version(parent, expected_version)
        if parent.approval_status.status_code not in {"DRAFT", "RETURNED", "APPROVED"}:
            raise ValidationError(
                "Membership actions require a draft, returned or approved activity."
            )
        row = StaffProfessionalMembership.objects.get(pk=pk)
        sources, target = LIFECYCLE[action]
        if row.membership_status not in sources:
            raise ValidationError(
                {"membership_status": "This transition is not allowed."}
            )
        before = lifecycle_values(row)
        if action == "renew":
            if (
                not isinstance(new_expiry_date, date)
                or new_expiry_date <= timezone.localdate()
                or (
                    row.membership_expiry_date
                    and new_expiry_date <= row.membership_expiry_date
                )
            ):
                raise ValidationError(
                    {
                        "new_expiry_date": "Choose a future date later than the current expiry."
                    }
                )
            row.membership_expiry_date = new_expiry_date
        elif new_expiry_date is not None:
            raise ValidationError(
                {"new_expiry_date": "Only renewal accepts a new expiry date."}
            )
        if (
            action == "reactivate"
            and row.membership_expiry_date
            and row.membership_expiry_date < timezone.localdate()
        ):
            raise ValidationError(
                {"membership_expiry_date": "Renew the expiry date before reactivation."}
            )
        if action == "mark-lifetime":
            row.is_lifetime_membership = True
            row.membership_expiry_date = None
            row.renewal_required = False
        row.membership_status = target
        normalize(row)
        row.save()
        parent.updated_by_user = fresh
        parent.save(update_fields=["updated_by_user", "updated_at"])
        record(
            actor=fresh,
            module=MODULE,
            action="UPDATE",
            entity=parent,
            details={
                "source": "lifecycle",
                "command": action,
                "remarks": remarks.strip(),
                "lifecycle_before": before,
                "lifecycle_after": lifecycle_values(row),
            },
        )
        return row

    return retry(
        actor,
        key,
        "membership." + action,
        {
            "pk": str(pk),
            "remarks": remarks,
            "version": expected_version,
            "new_expiry_date": new_expiry_date,
        },
        execute,
        "VERIFY",
    )


@command
def expire_one(actor, pk, as_of, dry_run=False):
    fresh, parent = locked(actor, pk, "VERIFY")
    require(fresh, "ACTIVITY", "READ", parent)
    row = StaffProfessionalMembership.objects.get(pk=pk)
    if (
        parent.approval_status.status_code not in {"DRAFT", "RETURNED", "APPROVED"}
        or row.membership_status != "ACTIVE"
        or row.is_lifetime_membership
        or not row.membership_expiry_date
        or row.membership_expiry_date >= as_of
    ):
        return False
    if not dry_run:
        before = lifecycle_values(row)
        row.membership_status = "EXPIRED"
        row.save(update_fields=["membership_status"])
        parent.updated_by_user = fresh
        parent.save(update_fields=["updated_by_user", "updated_at"])
        record(
            actor=fresh,
            module=MODULE,
            action="UPDATE",
            entity=parent,
            details={
                "source": "expiry_command",
                "as_of": str(as_of),
                "lifecycle_before": before,
                "lifecycle_after": lifecycle_values(row),
            },
        )
    return True
