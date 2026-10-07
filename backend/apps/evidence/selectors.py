from django.db.models import Count, Prefetch

from .models import EvidenceDocument, EvidenceDocumentTag
from .permissions import classification_scope, scope


def documents(actor, *, deleted=False, resource="DOCUMENT", action="READ"):
    rows = EvidenceDocument.all_objects.filter(
        scope(actor),
        scope(actor, resource, action),
        classification_scope(actor),
        staff_activity__deleted_at__isnull=True,
    )
    if deleted:
        rows = rows.filter(scope(actor, "TRASH"), deleted_at__isnull=False)
    else:
        rows = rows.filter(deleted_at__isnull=True, is_active=True)
    return (
        rows.select_related(
            "staff_activity__employee",
            "staff_activity__department",
            "document_type",
            "evidence_type",
            "confidentiality_level",
            "verification_status",
            "approval_status",
            "issuing_organization",
            "academic_year",
        )
        .prefetch_related(
            Prefetch(
                "tag_links",
                queryset=EvidenceDocumentTag.objects.select_related("evidence_tag"),
            )
        )
        .annotate(version_count=Count("versions", distinct=True))
        .order_by("-pk")
    )
