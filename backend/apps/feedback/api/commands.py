import hashlib,json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.exceptions import ValidationError,NotFound
from .serializers import COMMANDS
from .. import services as s,models as m,permissions as p
@s.command
def execute(*,actor,operation,data,key):
    if operation not in COMMANDS:raise NotFound()
    if not isinstance(key,str) or not key.strip() or len(key)>100:raise ValidationError('Supply an Idempotency-Key of 1-100 characters.')
    serializer,fn=COMMANDS[operation];parsed=serializer(data=data);parsed.is_valid(raise_exception=True);values=parsed.validated_data
    if operation=='bank':p.bank(actor,values['institution_id'],'manage_questionnaires' if values['resource']=='questionnaires' else 'manage_question_bank')
    elif operation in ['items','questionnaire-action']:p.bank(actor,m.Questionnaire.objects.get(pk=values['pk']).institution_id,'manage_questionnaires')
    elif operation=='create-cycle':p.schedule(actor,m.Questionnaire.objects.get(pk=values['questionnaire_id']),values['values'])
    else:p.cycle(actor,values['pk'],'override_cycle_state' if values.get('override') else 'manage_cycles')
    digest=hashlib.sha256(json.dumps({'operation':operation,'values':values},sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
    receipt=m.CommandReceipt.objects.filter(actor=actor,key=key).first()
    if receipt:
        if receipt.digest!=digest:raise s.Conflict('Retry key was used with different input.')
        return receipt.result
    token=s.key_context.set(key)
    try:
        obj=fn(actor=actor,**values);result={'id':str(obj.pk),'version':getattr(obj,'version',None),'resource':obj._meta.model_name}
        m.CommandReceipt.objects.create(actor=actor,key=key,digest=digest,result=result);return result
    finally:s.key_context.reset(token)
