"""Durable local event consumption. External delivery requires a configured adapter."""
from django.db import transaction
from . import models as m


def consume(consumer, handler, *, limit=100):
    """Handler and receipt commit together; handlers must only perform local DB work.

    An external adapter must send event_id as its idempotency key and maintain
    its own retryable delivery state. This function never sends notifications.
    """
    count = 0
    for event_id in m.OutboxEvent.objects.exclude(
        pk__in=m.EventReceipt.objects.filter(consumer=consumer).values('event_id'),
    ).order_by('pk').values_list('pk', flat=True)[:min(max(limit, 0), 1000)]:
        with transaction.atomic():
            event = m.OutboxEvent.objects.select_for_update().get(pk=event_id)
            if m.EventReceipt.objects.filter(event=event, consumer=consumer).exists():
                continue
            handler(event)
            m.EventReceipt.objects.create(event=event, consumer=consumer)
            count += 1
    return count
