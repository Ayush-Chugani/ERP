from contextvars import ContextVar

from apps.core.models import ReferenceAuditEvent

context = ContextVar("student_support_correlation", default="")


def emit(actor, obj, event, **metadata):
    # Never accept object snapshots or narrative fields here.
    allowed = {
        "status",
        "previous_status",
        "confidentiality_level",
        "previous_level",
        "history_id",
        "correlation",
    }
    if set(metadata) - allowed:
        raise ValueError("Unsupported audit metadata")
    return ReferenceAuditEvent.objects.create(
        actor=actor,
        action="create" if event.endswith("created") else "update",
        resource="m12_" + obj._meta.model_name,
        record_id=obj.pk,
        source="api",
        before={},
        after={"event": event, "correlation": context.get(), **metadata},
    )
