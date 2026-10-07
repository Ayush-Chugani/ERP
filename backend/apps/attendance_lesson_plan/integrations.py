"""M9 contracts. Missing calendar evidence is explicit, never assumed clear."""
from django.conf import settings
from django.utils.module_loading import import_string
from django.db import transaction
from . import models as m

def calendar_evidence(section,day):
    from .services import Conflict
    path=getattr(settings,'ATTENDANCE_CALENDAR_ADAPTER','')
    if not path:raise Conflict('Configure the attendance calendar/holiday provider before creating sessions.')
    result=import_string(path)(section=section,day=day)
    if not isinstance(result,dict) or result.get('status')!='INSTRUCTIONAL' or not isinstance(result.get('reference'),str) or not result['reference']:
        raise Conflict('Instructional-day evidence is unavailable or this is a non-instructional day.')
    return result['reference'][:200]

def deliver(consumer,callback,limit=100):
    count=0
    for pk in m.OutboxEvent.objects.exclude(pk__in=m.Delivery.objects.filter(consumer=consumer).values('event_id')).order_by('pk').values_list('pk',flat=True)[:limit]:
        with transaction.atomic():
            event=m.OutboxEvent.objects.select_for_update().get(pk=pk)
            if m.Delivery.objects.filter(event=event,consumer=consumer).exists():continue
            callback(str(event.pk),event.topic,event.payload)
            m.Delivery.objects.create(event=event,consumer=consumer);count+=1
    return count
