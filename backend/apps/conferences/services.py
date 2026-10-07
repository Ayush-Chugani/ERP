import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from apps.identity_access.audit import record
from apps.people_master.models import Employee, EmployeeAssignment
from apps.staff_activities.models import StaffActivity
from apps.staff_profile.models import ActivityType, ApprovalStatus, VerificationStatus

from .models import ConferenceActivity, ConferenceActivityIndexing, ConferenceEvent
from .permissions import principal, require
from .validators import active_references, normalize


class Conflict(APIException):
    status_code = 409
    default_detail = "The record conflicts with existing data or a newer edit."


def version(activity_id):
    parent = StaffActivity.objects.filter(pk=activity_id).values().get()
    child = ConferenceActivity.objects.filter(pk=activity_id).values().get()
    claims = list(
        ConferenceActivityIndexing.objects.filter(staff_activity_id=activity_id)
        .order_by("indexing_agency_id")
        .values()
    )
    return hashlib.sha256(
        json.dumps([parent, child, claims], sort_keys=True, default=str).encode()
    ).hexdigest()


def apply(row, values, excluded=()):
    allowed = {
        f.attname
        for f in row._meta.concrete_fields
        if not f.primary_key and not f.generated
    }
    allowed -= set(excluded) | {"created_at", "updated_at"}
    if set(values) - allowed:
        raise ValidationError("Unrecognized or protected fields.")
    for key, value in values.items():
        setattr(row, key, value)


def save_event(actor, values, *, event_id=None):
    actor = require(actor, "EVENT", "UPDATE" if event_id else "CREATE")
    try:
        with transaction.atomic():
            row = (
                ConferenceEvent.objects.select_for_update().get(pk=event_id)
                if event_id
                else ConferenceEvent()
            )
            old_dates = (row.start_date, row.end_date)
            apply(row, values)
            if (
                event_id
                and old_dates != (row.start_date, row.end_date)
                and ConferenceActivity.objects.filter(conference_event=row).exists()
            ):
                raise ValidationError(
                    "Dates of an event with recorded activities require a coordinated correction."
                )
            normalize(row)
            active_references(row)
            row.save()
            row.refresh_from_db()
            record(
                actor=actor,
                module="CONFERENCES",
                action="UPDATE" if event_id else "CREATE",
                entity=row,
                details={"fields": sorted(values)},
            )
            return row
    except ConferenceEvent.DoesNotExist:
        raise NotFound() from None
    except IntegrityError:
        raise Conflict() from None


def initial_status(model):
    # Do not invent official institutional status seeds.
    row = model.objects.filter(
        status_code="PENDING", is_active=True, is_terminal=False
    ).first()
    if row is None:
        raise ValidationError(
            "Configure an active nonterminal PENDING status before creating activities."
        )
    return row


def save_activity(
    actor,
    values,
    *,
    context=None,
    activity_id=None,
    expected_version=None,
    indexing=None,
):
    actor = principal(actor)
    try:
        with transaction.atomic():
            if activity_id:
                parent = StaffActivity.objects.select_for_update().get(
                    pk=activity_id, deleted_at__isnull=True
                )
                actor = require(actor, "ACTIVITY", "UPDATE", parent)
                if context:
                    raise ValidationError("Activity ownership cannot be replaced.")
                if expected_version is None or version(activity_id) != expected_version:
                    raise Conflict()
                row = ConferenceActivity.objects.get(pk=activity_id)
            else:
                context = dict(context or {})
                if set(context) - {
                    "employee_id",
                    "employee_assignment_id",
                    "activity_type_id",
                    "academic_year_id",
                }:
                    raise ValidationError("Unrecognized activity context.")
                employee = Employee.objects.select_for_update().get(
                    pk=context.get("employee_id")
                )
                event = ConferenceEvent.objects.select_for_update().get(
                    pk=values.get("conference_event_id"), is_active=True
                )
                assignment = EmployeeAssignment.objects.select_for_update().get(
                    pk=context.get("employee_assignment_id"), employee=employee
                )
                if (
                    assignment.campus.institution_id != employee.institution_id
                    or assignment.start_date > event.start_date
                    or (assignment.end_date and assignment.end_date < event.end_date)
                ):
                    raise ValidationError(
                        "Select an employee assignment valid for the event dates."
                    )
                kind = ActivityType.objects.get(
                    pk=context.get("activity_type_id"),
                    is_active=True,
                    activity_group="CONFERENCE",
                )
                parent = StaffActivity(
                    employee=employee,
                    institution_id=employee.institution_id,
                    campus_id=assignment.campus_id,
                    department_id=assignment.department_id,
                    activity_type=kind,
                    academic_year_id=context.get("academic_year_id"),
                    verification_status=initial_status(VerificationStatus),
                    approval_status=initial_status(ApprovalStatus),
                    created_by_user=actor,
                    start_date=event.start_date,
                    end_date=event.end_date,
                )
                actor = require(actor, "ACTIVITY", "CREATE", parent)
                row = ConferenceActivity(staff_activity=parent)
            from apps.staff_activities.specialization import ensure_exclusive

            ensure_exclusive(parent, ConferenceActivity)
            if parent.activity_type.activity_group != "CONFERENCE":
                raise ValidationError("Activity has an incompatible type.")
            if parent.pk and parent.approval_status.is_terminal:
                raise ValidationError(
                    "An approved or terminal activity cannot be edited through data entry."
                )
            old_event = row.conference_event_id
            apply(row, values)
            if activity_id and row.conference_event_id != old_event:
                raise ValidationError(
                    "Conference event cannot be replaced after creation."
                )
            normalize(row)
            active_references(row)
            parent.activity_title = (
                row.paper_title
                or row.presentation_title
                or row.conference_event.conference_title
            )
            parent.updated_by_user = actor
            parent.verification_status = initial_status(VerificationStatus)
            parent.verified_by_user = None
            parent.verified_at = None
            parent.verification_remarks = None
            parent.full_clean(validate_unique=False, validate_constraints=False)
            parent.save()
            row.staff_activity = parent
            row.save()
            if indexing is not None:
                agency_ids = [v.get("indexing_agency_id") for v in indexing]
                if len(agency_ids) != len(set(agency_ids)):
                    raise ValidationError("Duplicate indexing agencies.")
                existing = {
                    r.indexing_agency_id: r
                    for r in ConferenceActivityIndexing.objects.select_for_update().filter(
                        staff_activity=row
                    )
                }
                if any(r.indexing_status != "CLAIMED" for r in existing.values()):
                    raise ValidationError(
                        "Verified indexing requires the verification workflow."
                    )
                for data in indexing:
                    if set(data) - {"indexing_agency_id", "source_url", "remarks"}:
                        raise ValidationError(
                            "Indexing verification cannot be assigned by data entry."
                        )
                    claim = existing.get(
                        data["indexing_agency_id"]
                    ) or ConferenceActivityIndexing(staff_activity=row)
                    apply(
                        claim, data, excluded=("staff_activity_id", "indexing_status")
                    )
                    normalize(claim)
                    active_references(claim)
                    claim.save()
                ConferenceActivityIndexing.objects.filter(staff_activity=row).exclude(
                    indexing_agency_id__in=agency_ids
                ).delete()
            record(
                actor=actor,
                module="CONFERENCES",
                action="UPDATE" if activity_id else "CREATE",
                entity=row,
                details={
                    "fields": sorted(values),
                    "indexing_replaced": indexing is not None,
                },
            )
            return row
    except (
        StaffActivity.DoesNotExist,
        ConferenceActivity.DoesNotExist,
        Employee.DoesNotExist,
        EmployeeAssignment.DoesNotExist,
        ActivityType.DoesNotExist,
        ConferenceEvent.DoesNotExist,
    ):
        raise NotFound() from None
    except IntegrityError:
        raise Conflict() from None


def archive_activity(actor, activity_id, expected_version):
    with transaction.atomic():
        parent = StaffActivity.objects.select_for_update().get(
            pk=activity_id, deleted_at__isnull=True
        )
        actor = require(actor, "ACTIVITY", "DELETE", parent)
        if version(activity_id) != expected_version:
            raise Conflict()
        parent.deleted_at = timezone.now()
        parent.deleted_by_user = actor
        parent.updated_by_user = actor
        parent.save()
        record(actor=actor, module="CONFERENCES", action="DELETE", entity=parent)


def verify_indexing(
    actor, activity_id, agency_id, status, source_url, remarks, *, expected_version=None
):
    with transaction.atomic():
        parent = StaffActivity.objects.select_for_update().get(
            pk=activity_id, deleted_at__isnull=True
        )
        actor = require(actor, "ACTIVITY", "VERIFY", parent)
        from apps.people_master.models import AccountLink

        if (
            parent.created_by_user_id == actor.pk
            or AccountLink.objects.filter(
                employee_id=parent.employee_id, user=actor
            ).exists()
        ):
            raise PermissionDenied("An independent verifier is required.")
        if expected_version != version(activity_id):
            raise Conflict()
        row = ConferenceActivityIndexing.objects.select_for_update().get(
            staff_activity_id=activity_id, indexing_agency_id=agency_id
        )
        transitions = {
            "CLAIMED": {"VERIFIED", "NOT_INDEXED"},
            "VERIFIED": {"DISCONTINUED"},
            "DISCONTINUED": {"CLAIMED"},
            "NOT_INDEXED": {"CLAIMED"},
        }
        if (
            status not in transitions[row.indexing_status]
            or not source_url
            or not remarks
        ):
            raise ValidationError(
                "Select a valid transition with a source URL and remarks."
            )
        before = row.indexing_status
        row.indexing_status, row.source_url, row.remarks = status, source_url, remarks
        normalize(row)
        row.save()
        record(
            actor=actor,
            module="CONFERENCES",
            action="VERIFY",
            entity=parent,
            before={"indexing_status": before},
            after={"indexing_status": status},
            details={"indexing_agency_id": agency_id},
        )
        return row
