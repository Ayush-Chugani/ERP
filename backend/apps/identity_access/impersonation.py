from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, NotFound
from .services import authorize, reason
from .models import ImpersonationSession
from .evaluator import Scope, has_object_permission, usable
from .audit import record

# Only read-only support adapters may opt in. No legacy endpoint impersonation.
READ_ACTION='READ'

@transaction.atomic
def start(*,actor,target_id,proof,justification):
    actor=authorize(actor,'IMPERSONATE',proof)
    if actor.pk==target_id: raise PermissionDenied()
    if ImpersonationSession.objects.filter(actor=actor,ended_at__isnull=True,expires_at__gt=timezone.now()).exists():
        raise PermissionDenied('End the existing support session first.')
    target=get_user_model().objects.get(pk=target_id)
    if not usable(target,timezone.now()) or target.must_change_password: raise PermissionDenied()
    now=timezone.now()
    row=ImpersonationSession.objects.create(actor=actor,target=target,started_at=now,expires_at=now+timedelta(minutes=15),reason=reason(justification))
    record(actor=actor,action='IMPERSONATE',entity=row,details={'event':'start','target_user_id':target.pk,'reason':row.reason})
    return row

@transaction.atomic
def end(*,actor,session_id):
    row=ImpersonationSession.objects.select_for_update().filter(pk=session_id,actor=actor).first()
    if not row: raise NotFound()
    if row.ended_at is None:
        row.ended_at=timezone.now();row.save(update_fields=['ended_at'])
        record(actor=actor,action='IMPERSONATE',entity=row,details={'event':'end','target_user_id':row.target_id})
    return row


def context(*,actor,session_id):
    row=ImpersonationSession.objects.select_related('actor','target').filter(pk=session_id,actor=actor,ended_at__isnull=True,expires_at__gt=timezone.now()).first()
    if not row or not usable(row.actor,timezone.now()) or not usable(row.target,timezone.now()): raise PermissionDenied()
    if not has_object_permission(row.actor,'IAM.ALL.IMPERSONATE',scopes=[Scope('GLOBAL',0)]): raise PermissionDenied()
    return row


def allowed(*,actor,session_id,code,actor_scopes,target_scopes):
    row=context(actor=actor,session_id=session_id)
    parts=code.split('.')
    if len(parts)!=3 or parts[2]!=READ_ACTION or parts[0] in ('IAM','AUDIT'): return False
    return has_object_permission(row.actor,code,scopes=actor_scopes) and has_object_permission(row.target,code,scopes=target_scopes)
