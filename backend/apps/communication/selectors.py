from django.db.models import F, OuterRef, Q, Subquery
from django.utils import timezone

from apps.core.models import ReferenceAuditEvent

from . import models as m
from . import permissions as p


def feed(actor, at=None):
    at = at or timezone.now()
    return (
        p.recipients(actor, at)
        .filter(approval_status="APPROVED", publish_from__lte=at)
        .filter(Q(publish_to__isnull=True) | Q(publish_to__gt=at))
        .select_related("announcement_type", "department", "institution")
        .order_by("-publish_from", "-pk")
    )


def can_view(actor, pk, at=None):
    return feed(actor, at).filter(pk=pk).exists()


def type_by_code(code):
    return m.AnnouncementType.objects.filter(type_code=code, is_active=True).first()


def audit_rows(pk):
    return ReferenceAuditEvent.objects.filter(
        resource="m14_announcement", record_id=pk
    ).order_by("-pk")


def version(obj):
    if hasattr(obj, "workflow_version"):
        return str(obj.workflow_version or 0)
    return str(audit_rows(obj.pk).values_list("pk", flat=True).first() or 0)


def publication(obj, at=None):
    at = at or timezone.now()
    if obj.approval_status != "APPROVED":
        return obj.approval_status.lower()
    if at < obj.publish_from:
        return "scheduled"
    if obj.publish_to and at >= obj.publish_to:
        return "expired"
    return "published"


def summary(obj, management=False):
    data = {
        "id": str(obj.pk),
        "title": obj.title,
        "description": obj.description,
        "type": obj.announcement_type.type_name,
        "publish_from": obj.publish_from,
        "publish_to": obj.publish_to,
        "publisher": obj.department.department_name
        if obj.department_id
        else obj.institution.institution_name,
    }
    if management:
        data.update(
            status=obj.approval_status,
            publication=publication(obj),
            version=version(obj),
            institution_id=str(obj.institution_id),
            department_id=str(obj.department_id) if obj.department_id else None,
            announcement_type_id=str(obj.announcement_type_id),
            audience_type=obj.audience_type,
            programme_ids=[str(x.programme_id) for x in obj.programme_targets.all()],
            user_ids=[str(x.user_id) for x in obj.user_targets.all()],
        )
    return data


def attachment_rows(obj):
    return obj.attachments.order_by(
        F("display_order").asc(nulls_last=True), "file_object_id"
    )


def management_rows(qs):
    return (
        qs.select_related("announcement_type", "department", "institution")
        .prefetch_related("programme_targets", "user_targets")
        .annotate(
            workflow_version=Subquery(
                ReferenceAuditEvent.objects.filter(
                    resource="m14_announcement", record_id=OuterRef("pk")
                )
                .order_by("-pk")
                .values("pk")[:1]
            )
        )
    )
