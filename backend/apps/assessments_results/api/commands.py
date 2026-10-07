import hashlib,json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.exceptions import ValidationError,NotFound
from apps.term_registration import models as reg
from .. import services as s,permissions as p,models as m
from .serializers import COMMANDS

def authorize(actor,operation,data):
    if operation=='configure-scale':p.institution_access(actor,data['institution_id'])
    elif operation in ['component','configure-policy']:p.offering(actor,data['offering_id'],'configure')
    elif operation=='create-event':p.offering(actor,m.AssessmentComponent.objects.get(pk=data['component_id']).course_offering_id,'configure',event_id=0)
    elif operation=='update-event':s.event(actor,data['pk'],'configure')
    elif operation in ['mark','transition-event']:
        action='mark' if operation=='mark' else {'publish':'publish','reopen':'correct'}.get(data['action'],'configure')
        obj=s.event(actor,data.get('event_id',data.get('pk')),action)
        if operation=='mark':
            for row in data['entries']:s.authorize_registration(actor,obj,row['course_registration_id'])
    elif operation=='calculate-course':p.offering(actor,reg.StudentCourseRegistration.objects.get(pk=data['registration_id']).course_offering_id,'calculate',registration_id=data['registration_id'])
    elif operation=='calculate-term':s.result_offering(actor,m.StudentTermResult(term_registration_id=data['term_registration_id']),'calculate')
    else:
        obj=({'course':m.StudentCourseResult,'term':m.StudentTermResult}[data['resource']]).objects.get(pk=data['pk'])
        s.result_offering(actor,obj,'publish' if data['action']=='publish' else 'correct')
@s.command
def execute(*,actor,operation,data,key):
    if operation not in COMMANDS:raise NotFound()
    if not isinstance(key,str) or not key.strip() or len(key)>100:raise ValidationError('Idempotency-Key of 1-100 characters required.')
    parser,fn=COMMANDS[operation];parsed=parser(data=data);parsed.is_valid(raise_exception=True);values=parsed.validated_data
    authorize(actor,operation,values)
    digest=hashlib.sha256(json.dumps({'operation':operation,'data':values},sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
    receipt=m.Receipt.objects.filter(actor=actor,key=key).first()
    if receipt:
        if receipt.digest!=digest:raise s.Conflict('Idempotency key reused with different input.')
        return receipt.result
    token=s.key_context.set(key)
    try:
        obj=fn(actor=actor,**values);result={'id':str(obj.pk),'version':getattr(obj,'version',None),'resource':obj._meta.model_name}
        m.Receipt.objects.create(actor=actor,key=key,digest=digest,result=result);return result
    finally:s.key_context.reset(token)


@s.command
def execute_batch(*,actor,rows,key):
    if not isinstance(key,str) or not key.strip() or len(key)>80:raise ValidationError('Batch key must contain 1-80 characters.')
    if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValidationError('Batch requires 1-100 commands.')
    results=[]
    from rest_framework.exceptions import APIException
    for index,row in enumerate(rows):
        try:
            if not isinstance(row,dict) or set(row)!={'operation','data'}:raise ValidationError('Expected operation and data.')
            results.append(execute(actor=actor,operation=row['operation'],data=row['data'],key=key+':'+str(index)))
        except APIException as error:
            if error.status_code==409:raise s.Conflict({'rows':{str(index):error.detail}})
            raise ValidationError({'rows':{str(index):error.detail}})
    return results
