import hashlib,hmac,json,logging
from functools import wraps
from contextvars import ContextVar
from django.conf import settings
from django.db import transaction,IntegrityError,OperationalError
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelError,ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import APIException,ValidationError,NotFound
from . import models as m,permissions as p,validators as v
key_context=ContextVar('feedback_command',default='internal')
logger=logging.getLogger(__name__)
class Conflict(APIException):status_code=409;default_detail='Feedback conflicts with current state.';default_code='feedback_conflict'
def command(fn):
    @wraps(fn)
    def run(*,actor,**kw):
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='organization',model='university')
                actor=get_user_model().objects.get(pk=actor.pk)
                return fn(actor=actor,**kw)
        except (ValueError,TypeError):raise ValidationError('Invalid feedback input.') from None
        except ObjectDoesNotExist:raise NotFound('Feedback resource unavailable.') from None
        except ModelError as e:raise ValidationError(getattr(e,'message_dict',e.messages)) from None
        except (IntegrityError,OperationalError) as e:
            if e.args and e.args[0] in [1062,1451,1452,3819,4025,1205,1213]:raise Conflict('Concurrent or integrity conflict; refresh and retry.') from None
            raise
    return run
def packed(data):return json.loads(json.dumps(data,cls=DjangoJSONEncoder))
def snapshot(obj):return packed({f.attname:str(getattr(obj,f.attname)) if getattr(obj,f.attname) is not None and (f.primary_key or f.is_relation) else getattr(obj,f.attname) for f in obj._meta.concrete_fields})
def save(obj):obj.full_clean();obj.save();return obj
def version(obj,expected):
    if obj.version!=expected:raise Conflict('Stale version; refresh before applying changes.')
def audit(obj,actor,inst,action,reason,before=None):
    if not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise ValidationError('A reason up to 500 characters is required.')
    m.Audit.objects.create(institution_id=inst,actor=actor,resource=obj._meta.model_name,record_id=obj.pk,action=action,before=before or {},after=snapshot(obj),reason=reason,request_key=key_context.get())
    logger.info('feedback_admin_change',extra={'action':action,'resource':obj._meta.model_name,'record_id':obj.pk})
def updated(obj,actor,inst,action,reason,before):
    obj.actor=actor;obj.version+=1;save(obj);audit(obj,actor,inst,action,reason,before);return obj
BANK_MODELS={'categories':m.Category,'questions':m.Question,'choices':m.Choice,'questionnaires':m.Questionnaire}
ALLOWED={'categories':{'category_code','category_name','is_active'},'questions':{'feedback_category_id','question_text','response_type','is_active','rating_min','rating_max','rating_step','text_limit'},'choices':{'feedback_question_id','choice_text','score','display_order','is_active'},'questionnaires':{'questionnaire_code','questionnaire_name','questionnaire_type','is_anonymous'}}
def inst_of(obj):
    if isinstance(obj,(m.Category,m.Questionnaire)):return obj.institution_id
    return obj.feedback_category.institution_id if isinstance(obj,m.Question) else obj.feedback_question.feedback_category.institution_id
@command
def write_bank(*,actor,resource,institution_id,values,reason,pk=None,expected_version=None):
    if resource not in BANK_MODELS or set(values)-ALLOWED[resource]:raise ValidationError('Unknown resource or fields.')
    cap='manage_questionnaires' if resource=='questionnaires' else 'manage_question_bank';p.bank(actor,institution_id,cap)
    cls=BANK_MODELS[resource];obj=cls.objects.select_for_update().get(pk=pk) if pk else cls(actor=actor)
    if pk and inst_of(obj)!=institution_id:raise NotFound()
    before=snapshot(obj) if pk else {}
    if pk:
        version(obj,expected_version)
        if resource=='questionnaires' and obj.status!='DRAFT':raise Conflict('Only draft questionnaires are editable.')
        question=obj if resource=='questions' else obj.feedback_question if resource=='choices' else None
        if question and m.QuestionnaireItem.objects.filter(feedback_question=question).exclude(questionnaire__status='DRAFT').exists() and set(values)!={'is_active'}:raise Conflict('Referenced question content is frozen; author a new question.')
    if resource in ['categories','questionnaires']:obj.institution_id=institution_id
    for field,value in values.items():setattr(obj,field,value)
    if inst_of(obj)!=institution_id:raise ValidationError('Reference belongs to another institution.')
    if resource=='choices' and obj.feedback_question.response_type not in ['SINGLE_CHOICE','MULTIPLE_CHOICE']:raise ValidationError('Only selectable questions have choices; ratings are numeric.')
    return updated(obj,actor,institution_id,'bank_saved',reason,before)
@command
def replace_items(*,actor,pk,expected_version,items,reason):
    obj=m.Questionnaire.objects.select_for_update().get(pk=pk);p.bank(actor,obj.institution_id,'manage_questionnaires');version(obj,expected_version)
    if obj.status!='DRAFT':raise Conflict('Only draft items can be replaced.')
    if not 1<=len(items)<=100:raise ValidationError('Use 1-100 items.')
    if len({r['question_id'] for r in items})!=len(items) or len({r['display_order'] for r in items})!=len(items):raise ValidationError('Duplicate question or display order.')
    questions={q.pk:q for q in m.Question.objects.filter(pk__in=[r['question_id'] for r in items],feedback_category__institution_id=obj.institution_id)}
    if len(questions)!=len(items):raise ValidationError('Invalid question owner.')
    before=snapshot(obj);m.QuestionnaireItem.objects.filter(questionnaire=obj).delete()
    for row in items:save(m.QuestionnaireItem(questionnaire=obj,feedback_question=questions[row['question_id']],display_order=row['display_order'],is_required=row['is_required'],weightage=row.get('weightage')))
    return updated(obj,actor,obj.institution_id,'items_replaced',reason,before)
def readiness(obj):
    items=list(m.QuestionnaireItem.objects.filter(questionnaire=obj).select_related('feedback_question__feedback_category').order_by('display_order','pk'))
    choices={}
    for choice in m.Choice.objects.filter(feedback_question_id__in=[i.feedback_question_id for i in items],is_active=True).order_by('display_order','pk'):choices.setdefault(choice.feedback_question_id,[]).append({'id':str(choice.pk),'text':choice.choice_text,'score':str(choice.score) if choice.score is not None else None})
    if not items:raise ValidationError('Questionnaire is empty.')
    frozen=[]
    weighted=any(item.weightage is not None and item.weightage>0 for item in items)
    for item in items:
        question=item.feedback_question
        if not question.is_active or not question.feedback_category.is_active:raise ValidationError('Question/category is inactive.')
        question.full_clean();available=choices.get(question.pk,[])
        if question.response_type in ['SINGLE_CHOICE','MULTIPLE_CHOICE'] and not available:raise ValidationError('Selectable question has no active choices.')
        if weighted:
            if question.response_type=='TEXT' and item.weightage not in [None,0]:raise ValidationError('Text cannot carry a scoring weight.')
            if question.response_type!='TEXT':
                if item.weightage is None:raise ValidationError('Specify every scored item weight when using a weighted score.')
                if available and (any(c['score'] is None for c in available) or len({c['score'] for c in available})<2):raise ValidationError('Scored choices need nonconstant explicit scores.')
        frozen.append({'id':str(item.pk),'question_id':str(question.pk),'text':question.question_text,'response_type':question.response_type,'is_required':item.is_required,'weightage':str(item.weightage) if item.weightage is not None else None,'rating_min':str(question.rating_min) if question.rating_min is not None else None,'rating_max':str(question.rating_max) if question.rating_max is not None else None,'rating_step':str(question.rating_step) if question.rating_step is not None else None,'text_limit':question.text_limit,'choices':available})
    return {'name':obj.questionnaire_name,'type':obj.questionnaire_type,'anonymous':obj.is_anonymous,'items':frozen,'weighted':weighted}
@command
def questionnaire_action(*,actor,pk,expected_version,action,reason,code=None,name=None):
    obj=m.Questionnaire.objects.select_for_update().get(pk=pk);p.bank(actor,obj.institution_id,'manage_questionnaires');version(obj,expected_version);before=snapshot(obj)
    if action=='activate':
        if obj.status!='DRAFT':raise Conflict('Only a draft can activate.')
        readiness(obj);obj.status='ACTIVE'
    elif action=='retire':
        if obj.status!='ACTIVE':raise Conflict('Only active questionnaires retire.')
        obj.status='RETIRED'
    elif action=='clone':
        if not code or not name:raise ValidationError('Supply a new code and name.')
        clone=save(m.Questionnaire(institution_id=obj.institution_id,questionnaire_code=code,questionnaire_name=name,questionnaire_type=obj.questionnaire_type,is_anonymous=obj.is_anonymous,actor=actor))
        for item in m.QuestionnaireItem.objects.filter(questionnaire=obj):save(m.QuestionnaireItem(questionnaire=clone,feedback_question=item.feedback_question,display_order=item.display_order,is_required=item.is_required,weightage=item.weightage))
        audit(clone,actor,obj.institution_id,'questionnaire_cloned',reason);return clone
    else:raise ValidationError('Unknown questionnaire action.')
    return updated(obj,actor,obj.institution_id,'questionnaire_'+action,reason,before)
@command
def create_cycle(*,actor,questionnaire_id,values,reason):
    obj=m.Questionnaire.objects.get(pk=questionnaire_id)
    p.schedule(actor,obj,values)
    if obj.status!='ACTIVE':raise Conflict('Schedule an active questionnaire.')
    cycle=m.Cycle(questionnaire=obj,actor=actor,**values)
    if cycle.programme_id and cycle.programme.department.campus.institution_id!=obj.institution_id:raise ValidationError('Programme belongs to another institution.')
    if obj.questionnaire_type=='PROGRAMME' and not cycle.programme_id:raise ValidationError('Programme feedback requires a programme scope.')
    if obj.questionnaire_type=='EXIT' and cycle.target_policy!='COMPLETING':raise ValidationError('EXIT requires the completing-enrolment policy.')
    if obj.questionnaire_type=='OTHER' and cycle.target_policy!='EXPLICIT':raise ValidationError('OTHER requires explicit approved term registrations.')
    if obj.questionnaire_type not in ['EXIT','OTHER'] and cycle.target_policy!='ENROLLED':raise ValidationError('Use the enrolled policy for academic/institution targets.')
    if cycle.target_policy=='EXPLICIT':
        from apps.term_registration.models import StudentTermRegistration
        ids=cycle.explicit_registrations
        if not ids or len(ids)>500 or any(type(k)is not int or k<1 for k in ids):raise ValidationError('Use 1-500 explicit registration IDs.')
        qs=StudentTermRegistration.objects.filter(pk__in=ids,programme_term_offering__academic_term=cycle.academic_term,programme__department__campus__institution_id=obj.institution_id)
        if cycle.programme_id:qs=qs.filter(programme_id=cycle.programme_id)
        if qs.count()!=len(set(ids)):raise ValidationError('Invalid explicit registration scope.')
    elif cycle.explicit_registrations:raise ValidationError('Explicit registrations are only accepted for OTHER.')
    save(cycle);audit(cycle,actor,obj.institution_id,'cycle_created',reason);return cycle
def privacy_key():
    key=settings.FEEDBACK_PRIVACY_KEY
    if len(key)<32:raise Conflict('Configure a persistent feedback privacy key before opening cycles.')
    return key.encode()
def key_fingerprint():return hashlib.sha256(privacy_key()).hexdigest()
@command
def cycle_action(*,actor,pk,expected_version,action,reason,override=False):
    obj=p.cycle(actor,pk,'override_cycle_state' if override else 'manage_cycles',lock=True);version(obj,expected_version);before=snapshot(obj);now=timezone.now()
    if action=='open':
        if obj.status!='SCHEDULED' or now>=obj.end_at or (now<obj.start_at and not override):raise Conflict('Cycle is not eligible to open.')
        if obj.questionnaire.status!='ACTIVE':raise Conflict('Questionnaire must still be active.')
        obj.frozen=readiness(obj.questionnaire);obj.key_fingerprint=key_fingerprint();obj.status='OPEN'
        # An override changes status, but submission still starts at start_at.
    elif action=='close':
        if obj.status!='OPEN':raise Conflict('Only open cycles can close.')
        obj.status='CLOSED'
    elif action=='cancel':
        if obj.status not in ['SCHEDULED','OPEN']:raise Conflict('Closed/cancelled cycles are final.')
        obj.status='CANCELLED'
    else:raise ValidationError('Unknown cycle action.')
    return updated(obj,actor,obj.questionnaire.institution_id,'cycle_'+action,reason,before)


def fingerprint(value):return hmac.new(privacy_key(),json.dumps(value,sort_keys=True,separators=(',',':'),cls=DjangoJSONEncoder).encode(),hashlib.sha256).hexdigest()
@command
@sensitive_variables('answers','eligibility','identity','digest','prepared')
def submit(*,actor,cycle_id,target,answers,key):
    from .targets import POLICY
    if not isinstance(key,str) or not key.strip() or len(key)>100:raise ValidationError('Supply a retry key of 1-100 characters.')
    obj=m.Cycle.objects.select_for_update().select_related('questionnaire','academic_term','programme').get(pk=cycle_id)
    if obj.key_fingerprint!=key_fingerprint():raise Conflict('Cycle privacy key is unavailable or changed; operator action required.')
    eligibility=POLICY.validate_eligibility(actor,obj,target)
    identity=fingerprint({'cycle':obj.pk,'student':eligibility['student'],'target':eligibility['key']})
    digest=fingerprint({'key':key,'answers':answers,'target':eligibility['key']})
    previous=m.SubmissionLedger.objects.filter(cycle=obj,fingerprint=identity).first()
    if previous:
        if previous.request_digest!=digest:raise Conflict('Feedback was already submitted for this target.')
        return {'receipt':previous.receipt,'cycle_id':str(obj.pk),'status':'submitted'}
    now=timezone.now()
    if obj.status!='OPEN' or not obj.start_at<=now<obj.end_at:raise Conflict('Feedback cycle is not accepting submissions.')
    if not isinstance(answers,dict) or len(answers)>100 or len(json.dumps(answers))>1048576:raise ValidationError('Invalid or oversized answers.')
    items={item['id']:item for item in obj.frozen['items']}
    if set(answers)-set(items):raise ValidationError('Unknown questionnaire item.')
    prepared=[];errors={}
    for pk,item in items.items():
        if pk not in answers:
            if item['is_required']:errors[pk]='Answer required.'
            continue
        try:prepared.append((pk,v.answer(item,answers[pk])))
        except ValidationError as e:errors[pk]=e.detail
    if errors:raise ValidationError({'answers':errors})
    ledger=m.SubmissionLedger.objects.create(cycle=obj,fingerprint=identity,request_digest=digest)
    context=eligibility['context']
    response=m.Response.objects.create(feedback_cycle=obj,target_key=eligibility['key'],term_registration_id=None if obj.frozen['anonymous'] else eligibility['registration'],**context)
    for pk,value in prepared:
        selected=value.pop('choices',[])
        row=m.ResponseItem.objects.create(feedback_response=response,questionnaire_item_id=pk,**value)
        for choice in selected:m.ResponseItemChoice.objects.create(feedback_response_item=row,feedback_choice_id=choice)
    # No actor, answer, target or response ID is written to routine submission logs.
    logger.info('feedback_submission_accepted')
    return {'receipt':ledger.receipt,'cycle_id':str(obj.pk),'status':'submitted'}
