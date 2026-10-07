import logging
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.core.models import ReferenceAuditEvent
from apps.organization.models import Programme
from apps.tenancy.models import Membership

from . import models as m
from . import permissions as p
from . import selectors as q

log = logging.getLogger(__name__)
correlation = ContextVar("m14_correlation", default="")


class Conflict(APIException):
    status_code = 409
    default_code = "announcement_conflict"
    default_detail = "Announcement changed or workflow conflicts. Refresh and retry."


def command(fn):
    @wraps(fn)
    def run(*, actor, **kw):
        try:
            with transaction.atomic(durable=True):
                ContentType.objects.select_for_update().get(
                    app_label="organization", model="university"
                )
                actor = get_user_model().objects.get(pk=actor.pk)
                if not p.enabled(actor):
                    raise PermissionDenied()
                return fn(actor=actor, **kw)
        except ModelError as exc:
            raise ValidationError("Invalid announcement fields.") from exc
        except (IntegrityError, OperationalError) as exc:
            if exc.args and exc.args[0] in [1062, 1451, 1452, 3819, 4025, 1205, 1213]:
                raise Conflict() from None
            raise

    return run


def audit(actor, obj, event, previous=None, reason=None, changed=None):
    ReferenceAuditEvent.objects.create(
        actor=actor,
        action="create" if event == "created" else "update",
        resource="m14_announcement",
        record_id=obj.pk,
        source="api",
        before={"status": previous} if previous else {},
        after={
            "event": event,
            "correlation": correlation.get() or uuid4().hex,
            "status": obj.approval_status,
            "reason": reason,
            "changed": changed or [],
        },
    )
    log.info("m14_%s", event)


def reason_text(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValidationError("A reason of at most 500 characters is required.")
    return reason.strip()


def stale(obj, expected_version):
    if str(expected_version) != q.version(obj):
        raise Conflict()


def mutable(obj):
    if obj.approval_status not in ["DRAFT", "REJECTED"]:
        raise Conflict("Only drafts or rejected announcements may be edited.")


def validate(obj, programme_ids, user_ids):
    if (
        not obj.title.strip()
        or not obj.description.strip()
        or len(obj.description) > 50000
        or len(obj.description.encode("utf-8")) > 65535
    ):
        raise ValidationError(
            "Title and description are required; description limit is 50,000 characters."
        )
    if (
        not timezone.is_aware(obj.publish_from)
        or obj.publish_to
        and not timezone.is_aware(obj.publish_to)
    ):
        raise ValidationError("Timezone-aware publication times required.")
    if obj.publish_to and obj.publish_to <= obj.publish_from:
        raise ValidationError("Publication end must be later than start.")
    if not m.AnnouncementType.objects.filter(
        pk=obj.announcement_type_id, is_active=True
    ).exists():
        raise ValidationError("Active announcement type required.")
    if obj.audience_type == "DEPARTMENT" and not obj.department_id:
        raise ValidationError("Department audience requires a publishing department.")
    for ids in [programme_ids, user_ids]:
        if (
            len(ids) > 500
            or len(set(ids)) != len(ids)
            or any(type(x) is not int or x < 1 for x in ids)
        ):
            raise ValidationError("Targets must be unique positive IDs, at most 500.")
    if obj.audience_type == "PROGRAMME":
        if (
            not programme_ids
            or user_ids
            or Programme.objects.filter(
                pk__in=programme_ids,
                is_active=True,
                department__is_active=True,
                department__campus__is_active=True,
                department__campus__institution_id=obj.institution_id,
            ).count()
            != len(programme_ids)
        ):
            raise ValidationError("Select active programmes in the owning institution.")
    elif programme_ids:
        raise ValidationError("Programme targets require PROGRAMME audience.")
    if obj.audience_type == "CUSTOM":
        if (
            not user_ids
            or programme_ids
            or Membership.objects.filter(
                user_id__in=user_ids,
                is_active=True,
                user__is_active=True,
                institution_id=obj.institution_id,
            ).count()
            != len(user_ids)
        ):
            raise ValidationError("Select active members in the owning institution.")
    elif user_ids:
        raise ValidationError("User targets require CUSTOM audience.")
    obj.full_clean()


def audience_authority(actor, obj, cap):
    p.authorize_scope(actor, obj.institution_id, obj.department_id, cap)
    # Publishing beyond the owning department requires institution-level scope and capability.
    if obj.audience_type != "DEPARTMENT":
        p.authorize_scope(actor, obj.institution_id, None, cap)


def target_ids(obj):
    return list(obj.programme_targets.values_list("programme_id", flat=True)), list(
        obj.user_targets.values_list("user_id", flat=True)
    )


@command
def write(
    *,
    actor,
    pk=None,
    expected_version=None,
    programme_ids=None,
    user_ids=None,
    **fields,
):
    cap = "edit_announcement" if pk else "create_announcement"
    allowed = {
        "institution_id",
        "department_id",
        "announcement_type_id",
        "title",
        "description",
        "publish_from",
        "publish_to",
        "audience_type",
    }
    if set(fields) - allowed:
        raise ValidationError("Unknown or protected fields.")
    obj = p.get(p.management(actor, cap), pk, True) if pk else m.Announcement()
    if pk:
        stale(obj, expected_version)
        mutable(obj)
        if (
            "institution_id" in fields
            and fields["institution_id"] != obj.institution_id
        ):
            raise ValidationError("Ownership cannot change.")
    for name, value in fields.items():
        setattr(obj, name, value)
    programme_ids = (
        programme_ids
        if programme_ids is not None
        else (target_ids(obj)[0] if pk else [])
    )
    user_ids = user_ids if user_ids is not None else (target_ids(obj)[1] if pk else [])
    audience_authority(actor, obj, cap)
    validate(obj, programme_ids, user_ids)
    obj.save()
    obj.programme_targets.all().delete()
    obj.user_targets.all().delete()
    m.ProgrammeTarget.objects.bulk_create(
        [m.ProgrammeTarget(announcement=obj, programme_id=x) for x in programme_ids]
    )
    m.UserTarget.objects.bulk_create(
        [m.UserTarget(announcement=obj, user_id=x) for x in user_ids]
    )
    audit(
        actor, obj, "edited" if pk else "created", changed=sorted(fields) + ["targets"]
    )
    return obj


@command
def workflow(*, actor, pk, action, expected_version, reason):
    caps = {
        "submit": "submit_announcement",
        "approve": "approve_announcement",
        "reject": "reject_announcement",
        "revise": "edit_announcement",
        "archive": "archive_announcement",
    }
    if action not in caps:
        raise ValidationError("Unsupported action.")
    obj = p.get(p.management(actor, caps[action]), pk, True)
    stale(obj, expected_version)
    audience_authority(actor, obj, caps[action])
    reason = reason_text(reason)
    transitions = {
        "submit": ({"DRAFT"}, "PENDING"),
        "approve": ({"PENDING"}, "APPROVED"),
        "reject": ({"PENDING"}, "REJECTED"),
        "revise": ({"REJECTED"}, "DRAFT"),
        "archive": ({"DRAFT", "REJECTED", "PENDING", "APPROVED"}, "ARCHIVED"),
    }
    sources, target = transitions[action]
    if obj.approval_status not in sources:
        raise Conflict()
    if action in ["submit", "approve"]:
        validate(obj, *target_ids(obj))
        from apps.documents_exit.sharing import inspect_shared

        for link in obj.attachments.all():
            inspect_shared(
                actor=actor,
                file_id=link.file_object_id,
                institution_id=obj.institution_id,
            )
    if action == "approve":
        provenance = q.audit_rows(obj.pk)
        if (
            not provenance.filter(after__event="created").exists()
            or not provenance.filter(after__event="submit").exists()
        ):
            raise Conflict("Approval provenance missing.")
        if provenance.filter(
            after__event__in=["created", "submit"], actor=actor
        ).exists():
            raise PermissionDenied(
                "A different officer must approve this announcement."
            )
    previous = obj.approval_status
    obj.approval_status = target
    obj.save(update_fields=["approval_status"])
    audit(actor, obj, action, previous, reason)
    return obj


@command
def write_type(*, actor, type_code, type_name, is_active=True, pk=None):
    p.type_admin(actor)
    obj = (
        p.get(m.AnnouncementType.objects.all(), pk, True)
        if pk
        else m.AnnouncementType()
    )
    obj.type_code = type_code.strip().upper()
    obj.type_name = type_name.strip()
    obj.is_active = is_active
    obj.full_clean()
    obj.save()
    ReferenceAuditEvent.objects.create(
        actor=actor,
        action="update" if pk else "create",
        resource="m14_type",
        record_id=obj.pk,
        source="api",
        before={},
        after={"active": is_active},
    )
    return obj


def attachment_parent(actor, pk, expected_version):
    obj = p.get(p.management(actor, "manage_attachments"), pk, True)
    stale(obj, expected_version)
    mutable(obj)
    audience_authority(actor, obj, "manage_attachments")
    return obj


def add_link(actor, obj, file_id, display_order):
    if obj.attachments.count() >= 10:
        raise ValidationError("At most 10 attachments.")
    link = m.AnnouncementAttachment(
        announcement=obj, file_object_id=file_id, display_order=display_order
    )
    link.full_clean()
    link.save()
    audit(actor, obj, "attachment_added", changed=["attachments"])
    return obj


@command
def attachment(*, actor, pk, expected_version, action, file_id, display_order=None):
    obj = attachment_parent(actor, pk, expected_version)
    if action == "attach":
        from apps.documents_exit.sharing import inspect_shared

        inspect_shared(
            actor=actor, file_id=file_id, institution_id=obj.institution_id, manage=True
        )
        return add_link(actor, obj, file_id, display_order)
    link = obj.attachments.filter(file_object_id=file_id).first()
    if link is None:
        raise ValidationError("Attachment unavailable.")
    if action == "detach":
        link.delete()
    elif action == "reorder":
        link.display_order = display_order
        link.full_clean()
        link.save(update_fields=["display_order"])
    else:
        raise ValidationError("Unsupported attachment action.")
    audit(actor, obj, "attachment_" + action, changed=["attachments"])
    return obj


def upload_attachment(
    *, actor, pk, expected_version, upload, level="INTERNAL", display_order=None
):
    from apps.documents_exit.sharing import upload_shared

    def authorize(fresh_actor):
        return attachment_parent(fresh_actor, pk, expected_version)

    def attach(fresh_actor, obj, file):
        return add_link(fresh_actor, obj, file.pk, display_order)

    return upload_shared(
        actor=actor, upload=upload, level=level, authorize=authorize, attach=attach
    )
