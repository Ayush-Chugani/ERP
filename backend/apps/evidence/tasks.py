"""Scheduler-neutral expiry job; delivery is disabled unless an adapter is configured."""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from . import permissions as p
from . import selectors
from .models import EvidenceExpiryNotice

logger = logging.getLogger("sims.evidence")


def expiry_notices(*, actor, as_of, dry_run=True, limit=500, after_id=0):
    actor = p.principal(actor)
    thresholds = sorted(set(settings.EVIDENCE_EXPIRY_THRESHOLDS))
    if not thresholds or any(
        type(n) is not int or not 0 <= n <= 3660 for n in thresholds
    ):
        raise ValueError("Configure valid expiry thresholds.")
    from datetime import timedelta

    rows = (
        selectors.documents(actor)
        .filter(
            pk__gt=after_id,
            expiry_date__isnull=False,
            expiry_date__lte=as_of + timedelta(days=max(thresholds)),
        )
        .order_by("pk")[:limit]
    )
    result = {
        "candidates": 0,
        "created": 0,
        "delivered": 0,
        "failed": 0,
        "dry_run": dry_run,
        "as_of": as_of.isoformat(),
        "limit": limit,
        "next_after_id": None,
    }
    for row in rows:
        result["next_after_id"] = str(row.pk)
        remaining = (row.expiry_date - as_of).days
        threshold = next((n for n in thresholds if remaining <= n), None)
        if threshold is None:
            continue
        result["candidates"] += 1
        if dry_run:
            continue
        with transaction.atomic():
            # Serialize with evidence mutation and recheck scope/expiry immediately before queuing.
            from .models import EvidenceDocument

            locked = EvidenceDocument.all_objects.select_for_update().get(pk=row.pk)
            p.document(actor, locked)
            if locked.expiry_date != row.expiry_date:
                continue
            notice, created = EvidenceExpiryNotice.objects.get_or_create(
                document=locked,
                expiry_date=locked.expiry_date,
                threshold_days=threshold,
            )
            result["created"] += int(created)
        # Commit the outbox row before delivery; adapters deduplicate this stable event identity.
        with transaction.atomic():
            locked = EvidenceDocument.all_objects.select_for_update().get(pk=row.pk)
            p.document(actor, locked)
            if locked.expiry_date != row.expiry_date:
                continue
            notice = EvidenceExpiryNotice.objects.select_for_update().get(pk=notice.pk)
            if notice.delivered_at or not settings.EVIDENCE_NOTIFICATION_HANDLER:
                continue
            notice.attempts += 1
            notice.save(update_fields=["attempts"])
            try:
                import_string(settings.EVIDENCE_NOTIFICATION_HANDLER)(
                    event={
                        "event_id": f"evidence-expiry:{row.pk}:{row.expiry_date.isoformat()}:{threshold}",
                        "document_id": str(row.pk),
                        "actor_id": str(actor.pk),
                        "threshold_days": threshold,
                    }
                )
            except Exception:  # noqa: BLE001 - provider failures must not expose private metadata.
                logger.error(
                    "m33_expiry_delivery_failed",
                    extra={"record_id": row.pk, "notice_id": notice.pk},
                )
                result["failed"] += 1
            else:
                notice.delivered_at = timezone.now()
                notice.save(update_fields=["delivered_at"])
                result["delivered"] += 1
    logger.info(
        "m33_expiry_job",
        extra={
            "actor_id": actor.pk,
            "candidates": result["candidates"],
            "delivered": result["delivered"],
            "failed": result["failed"],
        },
    )
    return result
