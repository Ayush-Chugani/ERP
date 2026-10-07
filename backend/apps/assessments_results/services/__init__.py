"""Serialized, reauthorized academic commands and publication evidence."""
import hashlib,json
from contextvars import ContextVar
from functools import wraps
from decimal import Decimal
from django.db import transaction,IntegrityError,OperationalError
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ObjectDoesNotExist,ValidationError as ModelError
from django.utils import timezone
from django.db.models import Max,Q
from rest_framework.exceptions import APIException,ValidationError,NotFound,PermissionDenied
from apps.term_registration import models as reg
from .. import models as m,permissions as p,validators as v
key_context=ContextVar('m10_request',default='internal')
class Conflict(APIException):status_code=409;default_detail='Assessment state conflict.';default_code='assessment_conflict'
def command(fn):
    @wraps(fn)
    def run(*,actor,**kw):
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='organization',model='university')
                actor=get_user_model().objects.get(pk=actor.pk)
                return fn(actor=actor,**kw)
        except ObjectDoesNotExist:raise NotFound('Assessment resource unavailable.') from None
        except ModelError as e:raise ValidationError(getattr(e,'message_dict',e.messages)) from None
        except ValueError as e:raise ValidationError(str(e)) from None
        except (IntegrityError,OperationalError) as e:
            if e.args and e.args[0] in [1062,1451,1452,3819,4025,1205,1213]:raise Conflict('Concurrent or constraint conflict; refresh and retry.') from None
            raise
    return run
def packed(value):return json.loads(json.dumps(value,cls=DjangoJSONEncoder))
def snapshot(obj):return packed({f.attname:(str(getattr(obj,f.attname)) if getattr(obj,f.attname) is not None and (f.primary_key or f.is_relation) else getattr(obj,f.attname)) for f in obj._meta.concrete_fields})
def save(obj):obj.full_clean();obj.save();return obj
def version(obj,expected):
    if obj.version!=expected:raise Conflict('Stale version; refresh before retrying.')
def audit(obj,actor,action,reason,offering=None,institution_id=None,before=None):
    if not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise ValidationError('Supply a reason up to 500 characters.')
    m.Audit.objects.create(institution_id=institution_id or p.institution(offering),course_offering=offering,actor=actor,authority={'superuser':actor.is_superuser,'grants':list(p.grants(actor).values('id','role','campus_id','department_id'))},action=action,resource=obj._meta.model_name,record_id=obj.pk,before=before or {},after=snapshot(obj),reason=reason,request_key=key_context.get())
def update(obj,actor,action,reason,offering,before):
    obj.actor=actor;obj.version+=1;save(obj);audit(obj,actor,action,reason,offering,before=before);return obj
def event(actor,pk,action):
    obj=m.AssessmentEvent.objects.select_for_update().select_related('policy','assessment_component','course_offering__programme_term_offering__academic_term').get(pk=pk)
    p.offering(actor,obj.course_offering_id,action,day=obj.assessment_date,event_id=obj.pk);return obj
def eligible(obj):
    return reg.StudentCourseRegistration.objects.filter(course_offering_id=obj.course_offering_id,registration_status__in=['APPROVED','COMPLETED'],registration_date__lte=obj.assessment_date,term_registration__registration_status__in=['APPROVED','COMPLETED'])
def authorize_registration(actor,obj,registration_id,action='mark'):
    return p.offering(actor,obj.course_offering_id,action,day=obj.assessment_date,event_id=obj.pk,registration_id=registration_id)
@command
def configure_scale(*,actor,institution_id,values,rules,reason):
    p.institution_access(actor,institution_id);v.validate_bands(rules)
    scale=save(m.GradeScale(institution_id=institution_id,actor=actor,**values))
    for rule in rules:save(m.GradeRule(grade_scale=scale,**rule))
    audit(scale,actor,'scale_created',reason,institution_id=institution_id);return scale
@command
def configure_policy(*,actor,offering_id,grade_scale_id,expected_number,rules,reason):
    off=p.offering(actor,offering_id,'configure');v.validate_policy(rules)
    scale=m.GradeScale.objects.get(pk=grade_scale_id,institution_id=p.institution(off),is_active=True)
    if not m.GradeRule.objects.filter(grade_scale=scale,grade_letter=rules['failure_grade'],result_status='FAIL').exists():raise ValidationError('Threshold-failure grade must identify a FAIL rule.')
    if m.CalculationPolicy.objects.filter(course_offering=off).count()!=expected_number:raise Conflict('Stale policy revision.')
    if m.GradeRule.objects.filter(grade_scale=scale,grade_point__gt=v.number(rules['max_grade_point'])).exists():raise ValidationError('Grade points exceed policy scale.')
    obj=save(m.CalculationPolicy(course_offering=off,number=expected_number+1,grade_scale=scale,rules=packed(rules),actor=actor,reason=reason))
    audit(obj,actor,'policy_created',reason,off);return obj
@command
def component(*,actor,offering_id,values,reason,pk=None,expected_version=None):
    off=p.offering(actor,offering_id,'configure')
    obj=m.AssessmentComponent.objects.select_for_update().get(pk=pk,course_offering=off) if pk else m.AssessmentComponent(course_offering=off,actor=actor)
    before=snapshot(obj) if pk else {}
    if pk:
        version(obj,expected_version)
        if m.AssessmentEvent.objects.filter(assessment_component=obj).exists():raise Conflict('Used component structure is locked; create a successor component and policy.')
    for k,val in values.items():setattr(obj,k,val)
    return update(obj,actor,'component_saved',reason,off,before)
@command
def create_event(*,actor,component_id,policy_id,values,reason):
    component=m.AssessmentComponent.objects.get(pk=component_id);off=p.offering(actor,component.course_offering_id,'configure',day=values['assessment_date'],event_id=0)
    policy=m.CalculationPolicy.objects.get(pk=policy_id,course_offering=off)
    term=off.programme_term_offering.academic_term
    if not term.start_date<=values['assessment_date']<=term.end_date:raise ValidationError('Assessment date must fit its academic term.')
    if policy.rules['event_maximum']=='EQUAL_COMPONENT' and values['maximum_marks']!=component.maximum_marks:raise ValidationError('Policy requires the component maximum.')
    obj=save(m.AssessmentEvent(assessment_component=component,course_offering=off,policy=policy,actor=actor,**values))
    audit(obj,actor,'event_created',reason,off);return obj
@command
def transition_event(*,actor,pk,expected_version,action,reason):
    permission='publish' if action=='publish' else 'correct' if action=='reopen' else 'configure'
    obj=event(actor,pk,permission);version(obj,expected_version);before=snapshot(obj)
    off=p.offering(actor,obj.course_offering_id,permission,day=obj.assessment_date,event_id=obj.pk)
    if action=='conduct':
        if obj.status!='PLANNED' or obj.assessment_date>timezone.localdate():raise Conflict('Only a due planned event can be conducted.')
        roster=list(eligible(obj).values_list('pk',flat=True))
        if not roster or len(roster)>500:raise Conflict('Event requires 1-500 eligible registrations.')
        obj.roster=roster;obj.status='CONDUCTED'
    elif action=='cancel':
        if obj.status!='PLANNED':raise Conflict('Only a planned event can be cancelled.')
        obj.status='CANCELLED'
    elif action=='reopen':
        if obj.status!='PUBLISHED':raise Conflict('Only published events need correction reopening.')
        obj.status='CONDUCTED'
    elif action=='publish':
        if obj.status!='CONDUCTED':raise Conflict('Conduct the event before publishing.')
        if set(obj.roster)!=set(eligible(obj).values_list('pk',flat=True)):raise Conflict('Registration roster changed; reconcile upstream before publication.')
        marks=list(m.StudentAssessmentMark.objects.filter(assessment_event=obj))
        if {mark.course_registration_id for mark in marks}!=set(obj.roster):raise Conflict('Every registered student needs an explicit evaluation.')
        if any(mark.actor_id==actor.pk for mark in marks):raise PermissionDenied('A different authorized reviewer must publish entered marks.')
        obj.status='PUBLISHED'
    else:raise ValidationError('Unknown event transition.')
    update(obj,actor,'event_'+action,reason,off,before)
    if action=='publish':publish_snapshot(obj,actor,off,extra={'marks':[snapshot(mark) for mark in marks]})
    return obj
@command
def mark(*,actor,event_id,expected_version,entries,reason):
    obj=event(actor,event_id,'mark');version(obj,expected_version)
    if obj.status!='CONDUCTED':raise Conflict('Only conducted, unpublished events accept marks.')
    if not 1<=len(entries)<=500:raise ValidationError('Use 1-500 entries.')
    seen=set();errors={};prepared=[]
    for i,row in enumerate(entries):
        try:
            rid=row['course_registration_id'];authorize_registration(actor,obj,rid)
            if rid in seen or rid not in obj.roster or not eligible(obj).filter(pk=rid).exists():raise ValueError('Duplicate or ineligible registration.')
            seen.add(rid);status=row['attendance_status'];raw=row.get('marks_obtained');reduced=row.get('reduced_marks')
            if status!='PRESENT':
                if raw is not None or reduced is not None:raise ValueError('Special attendance requires null marks; policy determines its contribution.')
            else:
                if raw is None or not 0<=raw<=obj.maximum_marks:raise ValueError('Raw marks must be between zero and event maximum.')
                if obj.reduced_maximum_marks is not None:
                    expected=v.quantize(raw/obj.maximum_marks*obj.reduced_maximum_marks,obj.policy.rules)
                    if reduced is not None and reduced!=expected:raise ValueError('Reduced marks must equal the policy-rounded proportional value.')
                    reduced=expected
                elif reduced is not None:raise ValueError('Event has no reduced maximum.')
            existing=m.StudentAssessmentMark.objects.filter(assessment_event=obj,course_registration_id=rid).first()
            target=existing or m.StudentAssessmentMark(assessment_event=obj,course_registration_id=rid,course_offering_id=obj.course_offering_id,actor=actor)
            before=snapshot(existing) if existing else {};target.attendance_status=status;target.marks_obtained=raw;target.reduced_marks=reduced;target.remarks=row.get('remarks','');target.evaluated_at=timezone.now();prepared.append((target,before))
        except (ValueError,NotFound) as e:errors[str(i)]=str(e)
    if errors:raise ValidationError({'rows':errors})
    for target,before in prepared:update(target,actor,'mark_saved',reason,obj.course_offering,before)
    return update(obj,actor,'marks_saved',reason,obj.course_offering,snapshot(obj))
def publish_snapshot(obj,actor,off,extra=None):
    number=(m.Publication.objects.filter(resource=obj._meta.model_name,record_id=obj.pk).aggregate(n=Max('number'))['n'] or 0)+1
    return m.Publication.objects.create(institution_id=p.institution(off),resource=obj._meta.model_name,record_id=obj.pk,number=number,data={**snapshot(obj),**(extra or {})},actor=actor)
def latest(obj):return m.Publication.objects.filter(resource=obj._meta.model_name,record_id=obj.pk).order_by('-number').first()
def course_inputs(registration,attempt,policy):
    events=list(m.AssessmentEvent.objects.filter(course_offering=registration.course_offering,attempt_number=attempt).exclude(status='CANCELLED').select_related('assessment_component'))
    if not events or any(e.status!='PUBLISHED' or e.policy_id!=policy.pk for e in events):raise Conflict('All attempt events must be published under one policy.')
    components={e.assessment_component_id:e.assessment_component for e in events}
    all_components=list(m.AssessmentComponent.objects.filter(course_offering=registration.course_offering))
    if any(c.is_mandatory and c.pk not in components for c in all_components):raise Conflict('Mandatory component has no event.')
    if any(c.weightage_percent is None for c in all_components) or sum(c.weightage_percent for c in all_components)!=100:raise Conflict('Explicit component weights must total 100.')
    marks=list(m.StudentAssessmentMark.objects.filter(assessment_event__in=events,course_registration=registration).select_related('assessment_event'))
    if len(marks)!=len(events):raise Conflict('Missing event evaluation.')
    data={}
    for mark in marks:
        e=mark.assessment_event;data.setdefault(e.assessment_component_id,[]).append({'attendance_status':mark.attendance_status,'value':mark.reduced_marks if e.reduced_maximum_marks is not None else mark.marks_obtained,'maximum':e.reduced_maximum_marks or e.maximum_marks})
    score=v.InternalAssessmentPolicy.calculate([{'id':c.pk,'mandatory':c.is_mandatory,'weight':c.weightage_percent} for c in all_components],data,policy.rules)
    evidence={'events':{str(e.pk):e.version for e in events},'marks':{str(mark.pk):mark.version for mark in marks},'credits':str(registration.course_offering.course.credits),'course_id':registration.course_offering.course_id,'rules':policy.rules}
    return score,evidence
@command
def calculate_course(*,actor,registration_id,attempt,policy_id,external_percentage,expected_version,reason):
    registration=reg.StudentCourseRegistration.objects.select_related('course_offering__course','term_registration').get(pk=registration_id)
    off=p.offering(actor,registration.course_offering_id,'calculate',registration_id=registration.pk)
    if registration.registration_status not in ['APPROVED','COMPLETED']:raise Conflict('Approved registration required.')
    if registration.registration_type in ['AUDIT','CREDIT_TRANSFER']:raise Conflict('Audit and credit-transfer results need an approved programme-specific policy adapter.')
    policy=m.CalculationPolicy.objects.select_related('grade_scale').get(pk=policy_id,course_offering=off)
    day=off.programme_term_offering.academic_term.end_date
    if not policy.grade_scale.effective_from<=day or (policy.grade_scale.effective_to and day>policy.grade_scale.effective_to):raise Conflict('Grade scale is not effective at term end.')
    obj=m.StudentCourseResult.objects.select_for_update().filter(course_registration=registration,attempt_number=attempt).first()
    if (obj.version if obj else 0)!=expected_version:raise Conflict('Stale result version.')
    if obj and obj.state!='CALCULATED':raise Conflict('Explicitly reopen the result before recalculation.')
    internal,evidence=course_inputs(registration,attempt,policy);total,passed=v.CourseResultPolicy.calculate(internal,external_percentage,policy.rules)
    bands=list(m.GradeRule.objects.filter(grade_scale=policy.grade_scale).values('grade_letter','grade_point','minimum_percentage','maximum_percentage','result_status'))
    grade=v.resolve_grade(bands,total) if passed else next(b for b in bands if b['grade_letter']==policy.rules['failure_grade'])
    status=grade['result_status']
    before=snapshot(obj) if obj else {};obj=obj or m.StudentCourseResult(course_registration=registration,attempt_number=attempt,actor=actor)
    obj.policy=policy;obj.internal_marks=v.quantize(internal,policy.rules);obj.external_marks=v.quantize(external_percentage,policy.rules);obj.total_marks=v.quantize(total,policy.rules);obj.grade_letter=grade['grade_letter'];obj.grade_point=grade['grade_point'];obj.result_status=status;obj.result_date=timezone.localdate();obj.credits_earned=registration.course_offering.course.credits if status in policy.rules['credit_statuses'] else 0;obj.evidence=packed({**evidence,'calculated_by':actor.pk})
    return update(obj,actor,'course_calculated',reason,off,before)
def result_offering(actor,obj,action):
    if isinstance(obj,m.StudentCourseResult):return p.offering(actor,obj.course_registration.course_offering_id,action,registration_id=obj.course_registration_id)
    regs=list(reg.StudentCourseRegistration.objects.filter(term_registration=obj.term_registration).exclude(registration_status__in=['DROPPED','WITHDRAWN']))
    if not regs:raise Conflict('Empty term registration.')
    for registration in regs:p.offering(actor,registration.course_offering_id,action,registration_id=registration.pk)
    return regs[0].course_offering
@command
def transition_result(*,actor,resource,pk,expected_version,action,reason):
    model={'course':m.StudentCourseResult,'term':m.StudentTermResult}[resource];obj=model.objects.select_for_update().get(pk=pk)
    off=result_offering(actor,obj,'publish' if action=='publish' else 'correct');version(obj,expected_version);before=snapshot(obj)
    if action=='publish':
        if obj.state!='CALCULATED':raise Conflict('Only calculated results can be published.')
        if obj.evidence.get('calculated_by')==actor.pk:raise PermissionDenied('A different authorized reviewer must publish.')
        if resource=='course':
            _,current=course_inputs(obj.course_registration,obj.attempt_number,obj.policy)
            if packed(current)!={k:value for k,value in obj.evidence.items() if k!='calculated_by'}:raise Conflict('Calculation inputs changed; recalculate.')
        else:
            current=term_data(obj.term_registration)
            if current['evidence']!={k:value for k,value in obj.evidence.items() if k!='calculated_by'}:raise Conflict('Term inputs changed; recalculate.')
        obj.state='PUBLISHED';obj.is_withheld=False
        if resource=='term':obj.published_at=timezone.now()
    elif action=='reopen':
        if obj.state not in ['PUBLISHED','WITHHELD']:raise Conflict('Only a published or withheld result can be reopened.')
        obj.state='CALCULATED'
    elif action=='withhold':
        if obj.state=='WITHHELD':raise Conflict('Already withheld.')
        obj.state='WITHHELD';obj.is_withheld=True
    else:raise ValidationError('Unknown result transition.')
    update(obj,actor,'result_'+action,reason,off,before)
    if action=='publish':publish_snapshot(obj,actor,off)
    return obj
def authoritative(registration):
    results=list(m.StudentCourseResult.objects.filter(course_registration=registration).select_related('policy'))
    values=[]
    for result in results:
        pub=latest(result)
        if result.is_withheld:raise Conflict('A course result is withheld.')
        if pub:values.append((result,pub))
    if not values:raise Conflict('A registered course lacks a published result.')
    modes={pub.data['evidence']['rules']['repeat'] for _,pub in values}
    if len(modes)!=1:raise Conflict('Repeat policies disagree across published attempts.')
    mode=modes.pop()
    return max(values,key=lambda pair:(v.number(pair[1].data['grade_point']),pair[0].attempt_number) if mode=='BEST' else pair[0].attempt_number)
def term_data(term):
    registrations=list(reg.StudentCourseRegistration.objects.filter(term_registration=term,registration_status__in=['APPROVED','COMPLETED']).select_related('course_offering'))
    if not registrations:raise Conflict('No approved course registrations.')
    selected=[authoritative(row) for row in registrations];rules=selected[0][1].data['evidence']['rules']
    formula_keys=['repeat','gpa_statuses','credit_statuses','max_grade_point','rounding']
    if any(any(pub.data['evidence']['rules'][k]!=rules[k] for k in formula_keys) for _,pub in selected):raise Conflict('Incompatible term GPA policies.')
    def item(pair):
        _,pub=pair;return {'credits':pub.data['evidence']['credits'],'grade_point':pub.data['grade_point'],'result_status':pub.data['result_status'],'earned':pub.data['credits_earned']}
    current=[item(pair) for pair in selected]
    prior=list(reg.StudentTermRegistration.objects.filter(enrolment=term.enrolment,programme_term_offering__academic_term__end_date__lt=term.programme_term_offering.academic_term.start_date,registration_status__in=['APPROVED','COMPLETED']).select_related('programme_term_offering__academic_term').order_by('programme_term_offering__academic_term__end_date','pk'))
    history=[]
    for previous in prior:
        for registration in reg.StudentCourseRegistration.objects.filter(term_registration=previous,registration_status__in=['APPROVED','COMPLETED']):history.append(authoritative(registration))
    all_pairs=history+selected;by_course={}
    for pair in all_pairs:
        result,pub=pair
        if any(pub.data['evidence']['rules'][k]!=rules[k] for k in formula_keys):raise Conflict('Incompatible cumulative GPA policies.')
        course=pub.data['evidence']['course_id'];existing=by_course.get(course)
        if existing is None or rules['repeat']=='LATEST' or v.number(pub.data['grade_point'])>v.number(existing[1].data['grade_point']):by_course[course]=pair
    return {'credits_registered':sum(v.number(x['credits']) for x in current),'credits_earned':sum(v.number(x['earned']) for x in current),'sgpa':v.TermGpaPolicy.calculate(current,rules),'cgpa':v.TermGpaPolicy.calculate([item(pair) for pair in by_course.values()],rules),'result_status':'PASS' if all(x['result_status'] in rules['credit_statuses'] for x in current) else 'FAIL','evidence':packed({'publications':sorted(pub.pk for _,pub in all_pairs),'rules':rules,'registrations':sorted(row.pk for row in registrations)})}
@command
def calculate_term(*,actor,term_registration_id,expected_version,reason):
    term=reg.StudentTermRegistration.objects.get(pk=term_registration_id)
    obj=m.StudentTermResult.objects.select_for_update().filter(term_registration=term).first()
    if (obj.version if obj else 0)!=expected_version:raise Conflict('Stale term result.')
    obj=obj or m.StudentTermResult(term_registration=term,actor=actor)
    off=result_offering(actor,obj,'calculate')
    if obj.state!='CALCULATED':raise Conflict('Reopen published term results first.')
    before=snapshot(obj)
    for name,value in term_data(term).items():setattr(obj,name,value)
    obj.evidence['calculated_by']=actor.pk
    return update(obj,actor,'term_calculated',reason,off,before)


@command
def update_event(*,actor,pk,expected_version,values,reason):
    obj=event(actor,pk,'configure');version(obj,expected_version)
    if obj.status!='PLANNED':raise Conflict('Only planned events can be structurally edited.')
    off=p.offering(actor,obj.course_offering_id,'configure',day=values['assessment_date'],event_id=obj.pk)
    term=off.programme_term_offering.academic_term
    if not term.start_date<=values['assessment_date']<=term.end_date:raise ValidationError('Event date must fit the term.')
    if obj.policy.rules['event_maximum']=='EQUAL_COMPONENT' and values['maximum_marks']!=obj.assessment_component.maximum_marks:raise ValidationError('Policy requires the component maximum.')
    before=snapshot(obj)
    for field,value in values.items():setattr(obj,field,value)
    return update(obj,actor,'event_updated',reason,off,before)
