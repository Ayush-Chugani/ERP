from rest_framework import serializers as z
from rest_framework.exceptions import ValidationError,NotFound,PermissionDenied
from decimal import Decimal
from . import services as s,models as m
from .policies import require_section,require_session,own_student

class Strict(z.Serializer):
    def to_internal_value(self,data):
        if not isinstance(data,dict):raise ValidationError('Expected an object.')
        if set(data)-set(self.fields):raise ValidationError({key:'Unknown field.' for key in set(data)-set(self.fields)})
        return super().to_internal_value(data)
def ID(**kwargs):return z.IntegerField(min_value=1,**kwargs)
def Reason():return z.CharField(max_length=500,allow_blank=False)
def schema(name,**fields):return type('Attendance'+name,(Strict,),fields)
Weight=schema('Weight',credit=z.DecimalField(max_digits=5,decimal_places=4,min_value=0,max_value=1),denominator=z.DecimalField(max_digits=5,decimal_places=4,min_value=0,max_value=1))
Policy=schema('Policy',section_id=ID(),expected_number=z.IntegerField(min_value=0),basis=z.ChoiceField(choices=['SESSION','DURATION']),rules=z.DictField(child=Weight()),threshold=z.DecimalField(max_digits=5,decimal_places=2,min_value=0,max_value=100),edit_days=z.IntegerField(min_value=0,max_value=3650),correction_days=z.IntegerField(min_value=0,max_value=3650),reason=Reason())
Session=schema('Session',section_id=ID(),occurrence_id=ID(required=False),faculty_assignment_id=ID(required=False),room_id=ID(required=False),session_date=z.DateField(required=False),start_time=z.TimeField(required=False),end_time=z.TimeField(required=False),source_session_id=ID(required=False),reason=Reason())
Transition=schema('Transition',session_id=ID(),expected_version=ID(),action=z.ChoiceField(choices=['conduct','open','finalize','reopen','cancel']),reason=Reason())
Entry=schema('Entry',attendance_id=ID(),status_id=ID(),remarks=z.CharField(max_length=500,required=False,allow_blank=True))
Mark=schema('Mark',session_id=ID(),expected_version=ID(),entries=Entry(many=True,min_length=1,max_length=500),reason=Reason())
Correction=schema('Correction',attendance_id=ID(),expected_version=ID(),status_id=ID(),reason=z.CharField(max_length=1000),evidence_reference=z.CharField(max_length=200,required=False,allow_blank=True))
Decision=schema('Decision',correction_id=ID(),expected_version=ID(),decision=z.ChoiceField(choices=['APPROVED','REJECTED','CANCELLED']),reason=z.CharField(max_length=1000))
Topic=schema('Topic',key=z.CharField(max_length=50),title=z.CharField(max_length=200),planned_date=z.DateField(),minutes=z.IntegerField(min_value=1,max_value=10000),method=z.CharField(max_length=100),outcomes=z.CharField(max_length=1000,allow_blank=True))
Lessons=schema('Lessons',section_id=ID(),expected_number=z.IntegerField(min_value=0),topics=Topic(many=True,min_length=1,max_length=200),reason=Reason())
Coverage=schema('Coverage',session_id=ID(),expected_version=ID(),lesson_revision_id=ID(),topic_key=z.CharField(max_length=50),percent=z.DecimalField(max_digits=5,decimal_places=2,min_value=Decimal('.01'),max_value=100),minutes=z.IntegerField(min_value=1,max_value=1440),reason=Reason())
Result=schema('Result',id=z.CharField(),version=z.IntegerField(allow_null=True),resource=z.CharField())
Reconcile=schema('Reconcile',session_id=ID(),expected_version=ID(),reason=Reason())
COMMANDS={
    'reconcile-register':(Reconcile,s.reconcile_register),
    'configure-policy':(Policy,s.configure_policy),'create-session':(Session,s.create_session),
    'transition-session':(Transition,s.transition_session),'mark':(Mark,s.mark),
    'request-correction':(Correction,s.request_correction),'decide-correction':(Decision,s.decide_correction),
    'revise-lessons':(Lessons,s.revise_lessons),'record-coverage':(Coverage,s.record_coverage),
}

def authorize(actor,operation,data):
    if operation in ['configure-policy','revise-lessons','create-session']:
        action='configure_attendance' if operation=='configure-policy' else 'exceptional_attendance' if operation=='create-session' and not data.get('occurrence_id') else 'manage_attendance'
        require_section(actor,data['section_id'],action,data.get('session_date'))
        if operation=='create-session':
            if not data.get('occurrence_id') and not all(data.get(key) is not None for key in ['faculty_assignment_id','room_id','session_date','start_time','end_time']):raise ValidationError('Exceptional sessions require faculty, room, date and times.')
            if data.get('occurrence_id'):
                source,row,_=s.resolved_occurrence(data['occurrence_id'])
                if row.section_id!=data['section_id']:raise NotFound()
                require_section(actor,data['section_id'],action,row.day)
                existing=m.ClassSession.objects.filter(occurrence_id=data['occurrence_id']).first()
                if existing:require_session(actor,existing,action)
            if data.get('source_session_id'):s.session_for(actor,data['source_session_id'],'exceptional_attendance')
    elif 'session_id' in data:
        action='review_attendance' if operation=='reconcile-register' else 'manage_attendance' if operation=='record-coverage' or data.get('action')=='cancel' else 'reopen_attendance' if data.get('action')=='reopen' else 'mark_attendance'
        s.session_for(actor,data['session_id'],action)
    else:
        correction=m.CorrectionRequest.objects.get(pk=data['correction_id']) if operation=='decide-correction' else None
        row=m.StudentAttendance.objects.select_related('class_session').get(pk=correction.attendance_id if correction else data['attendance_id'])
        if correction and data['decision']!='CANCELLED':
            require_session(actor,row.class_session,'review_attendance')
            if correction.requested_by_id==actor.pk:raise PermissionDenied('A different reviewer is required.')
        else:
            if correction and correction.requested_by_id!=actor.pk:raise PermissionDenied()
            try:require_session(actor,row.class_session,'mark_attendance')
            except NotFound:
                if own_student(actor)!=row.student_id:raise NotFound()

@s.command
def execute(*,actor,operation,data,key):
    import hashlib,json
    from django.core.serializers.json import DjangoJSONEncoder
    if operation not in COMMANDS:raise NotFound()
    if not isinstance(key,str) or not key.strip() or len(key)>100:raise ValidationError('Supply an Idempotency-Key of 1–100 characters.')
    parser,handler=COMMANDS[operation]
    parsed=parser(data=data);parsed.is_valid(raise_exception=True);values=parsed.validated_data
    authorize(actor,operation,values)
    fingerprint=hashlib.sha256(json.dumps({'operation':operation,'data':values},sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()
    receipt=m.CommandReceipt.objects.filter(actor=actor,key=key).first()
    if receipt:
        if receipt.digest!=fingerprint:raise s.Conflict('Idempotency key already used for different input.')
        return receipt.result
    token=s.request_key.set(key)
    try:
        if operation=='configure-policy':values['rules']=json.loads(json.dumps(values['rules'],cls=DjangoJSONEncoder))
        result=handler(actor=actor,**values)
        response={'id':str(result.pk),'version':getattr(result,'version',None),'resource':result._meta.model_name}
        m.CommandReceipt.objects.create(actor=actor,key=key,digest=fingerprint,result=response)
        s.logger.info('attendance_command',extra={'operation':operation,'actor_id':actor.pk,'request_key':key})
        return response
    finally:s.request_key.reset(token)
