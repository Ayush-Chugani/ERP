import json
import logging
from contextvars import ContextVar

from django.core.serializers.json import DjangoJSONEncoder

from apps.identity_access.audit import record as platform_record

from .models import EvidenceDocument, EvidenceDocumentAudit

request_context = ContextVar("m33_request_context", default=None)
logger = logging.getLogger("sims.evidence")


def write(actor, row, action, *, version=None, before=None, after=None, remarks=None):
    ctx = request_context.get() or {}
    event = EvidenceDocumentAudit.objects.create(
        evidence_document=row,
        evidence_document_version=version,
        action_code=action,
        performed_by_user=actor,
        ip_address=ctx.get("ip"),
        user_agent=ctx.get("user_agent"),
        before_values=json.loads(json.dumps(before, cls=DjangoJSONEncoder))
        if before is not None
        else None,
        after_values=json.loads(json.dumps(after, cls=DjangoJSONEncoder))
        if after is not None
        else None,
        remarks=remarks,
    )
    platform_record(
        actor=actor,
        module="EVIDENCE",
        action=action,
        entity=row,
        details={
            "evidence_audit_id": event.pk,
            "version_id": version.pk if version else None,
            "fields": sorted(after or {}),
        },
        request_id=ctx.get("id"),
        ip=ctx.get("ip"),
    )
    return event


def denied(actor, document_id):
    if (
        (request_context.get() or {}).get("denied_recorded")
        or not document_id
        or not actor
        or not actor.is_authenticated
    ):
        return
    try:
        row = EvidenceDocument.all_objects.filter(pk=document_id).first()
        if row:
            write(actor, row, "ACCESS_DENIED", remarks="Requested action denied.")
            if request_context.get():
                request_context.get()["denied_recorded"] = True
    except Exception:  # noqa: BLE001 - failed denial auditing must not disclose evidence.
        logger.error(
            "m33_denied_audit_failed",
            extra={
                "actor_id": actor.pk,
                "record_id": document_id,
                "request_identifier": (request_context.get() or {}).get("id"),
            },
        )
