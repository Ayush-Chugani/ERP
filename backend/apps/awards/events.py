"""After-commit integration boundary; delivery belongs to the configured shared adapter."""

import logging

from django.conf import settings
from django.db import transaction
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def committed(history):
    adapter = getattr(settings, "AWARDS_EVENT_HANDLER", None)
    if not adapter or history.to_status.status_code not in {
        "SUBMITTED",
        "RETURNED",
        "APPROVED",
        "REJECTED",
    }:
        return
    event = {
        "event_id": "awards-status:" + str(history.pk),
        "activity_id": str(history.activity_id),
        "status": history.to_status.status_code,
        "actor_id": str(history.changed_by_id),
    }

    def deliver():
        try:
            # Adapter resolves configured recipients and queues through shared infrastructure.
            # It must deduplicate event_id. Immutable history remains available for reconciliation.
            import_string(adapter)(event=event)
        except Exception:  # noqa: BLE001 - delivery failure must not roll back committed business data.
            logger.error("awards_event_delivery_failed event_id=%s", event["event_id"])

    transaction.on_commit(deliver)
