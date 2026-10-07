"""Idempotent, bounded atomic execution shared by HTTP and controlled imports."""
import hashlib
import json
import logging
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from rest_framework.exceptions import ValidationError
from . import models as m
from .services import command, RegistrationConflict
from .selectors import record

logger = logging.getLogger(__name__)


@command
def execute(*, actor, operation, data, key, dry_run=False):
    from .commands import COMMANDS, authorize
    if not isinstance(key,str) or not key.strip() or len(key)>100:
        raise ValidationError('Supply an Idempotency-Key of 1–100 characters.')
    if operation not in COMMANDS: raise ValidationError('Unknown registration command.')
    serializer, handler = COMMANDS[operation]
    parsed = serializer(data=data); parsed.is_valid(raise_exception=True)
    values = parsed.validated_data
    authorize(actor,operation,values)
    digest = hashlib.sha256(json.dumps({'operation':operation,'data':values},sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
    receipt = m.CommandReceipt.objects.filter(actor=actor,key=key).first()
    if receipt:
        if receipt.digest != digest: raise RegistrationConflict('Idempotency key was already used for different input.')
        return receipt.result
    obj = handler(actor=actor,**values)
    result = {'id':str(obj.pk),'version':getattr(obj,'version',None),'resource':obj._meta.model_name}
    m.CommandReceipt.objects.create(actor=actor,key=key,digest=digest,result=result)
    logger.info('registration_command',extra={'operation':operation,'actor_id':actor.pk,'request_key':key,'dry_run':dry_run})
    if dry_run: transaction.set_rollback(True)
    return result


@command
def bulk(*, actor, rows, key, dry_run=True):
    if not isinstance(rows,list) or not 1 <= len(rows) <= 100:
        raise ValidationError('Submit between 1 and 100 command rows.')
    if not isinstance(key,str) or not key.strip() or len(key)>80: raise ValidationError('Bulk key must contain 1–80 characters.')
    from .commands import COMMANDS, authorize
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
    existing=m.CommandReceipt.objects.filter(actor=actor,key=key).first()
    if existing and existing.digest!=digest: raise RegistrationConflict('Bulk key was already used for another batch.')
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'operation','data'} or row['operation'] not in COMMANDS:
            raise ValidationError('Each row needs a known operation and data.')
        parsed=COMMANDS[row['operation']][0](data=row['data']);parsed.is_valid(raise_exception=True)
        authorize(actor,row['operation'],parsed.validated_data)
    if existing: return existing.result['results']
    results = []
    for index,row in enumerate(rows):
        if not isinstance(row,dict) or set(row) != {'operation','data'}:
            raise ValidationError({'row':index+1,'detail':'Each row needs operation and data only.'})
        try: results.append(execute(actor=actor,operation=row['operation'],data=row['data'],key=f'{key}:{index}'))
        except (ValidationError,RegistrationConflict) as exc:
            raise ValidationError({'row':index+1,'detail':exc.detail}) from None
    m.CommandReceipt.objects.create(actor=actor,key=key,digest=digest,result={'results':results})
    if dry_run: transaction.set_rollback(True)
    return results
