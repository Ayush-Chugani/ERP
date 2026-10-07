from collections import Counter,defaultdict
from decimal import Decimal
from statistics import median
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import NotFound,ValidationError,PermissionDenied
from apps.people_master.models import AccountLink
from apps.teaching_timetable.models import FacultyAssignment
from . import models as m,permissions as p,services as s
from .targets import POLICY

def available(actor):
    if not p.enabled(actor,'submit_feedback'):raise PermissionDenied()
    link=AccountLink.objects.filter(user=actor,student__isnull=False).select_related('student').first()
    if not link:raise NotFound()
    now=timezone.now();qs=m.Cycle.objects.filter(questionnaire__institution=link.student.institution,status='OPEN',start_at__lte=now,end_at__gt=now).select_related('questionnaire','academic_term','programme')
    if qs.count()>100:raise ValidationError('Too many open cycles; contact the feedback coordinator.')
    results=[]
    for obj in qs:
        for target in POLICY.targets(actor,obj):results.append({'cycle_id':str(obj.pk),'name':obj.cycle_name,'anonymous':obj.frozen['anonymous'],'end_at':obj.end_at,**target})
    if len(results)>500:raise ValidationError('Too many feedback targets.')
    return results

def questionnaire(actor,pk,target):
    obj=m.Cycle.objects.select_related('questionnaire','academic_term','programme').get(pk=pk)
    POLICY.validate_eligibility(actor,obj,target)
    now=timezone.now()
    if obj.status!='OPEN' or not obj.start_at<=now<obj.end_at:raise s.Conflict('Cycle is not accepting feedback.')
    return {'cycle_id':str(obj.pk),'name':obj.cycle_name,'anonymous':obj.frozen['anonymous'],'items':obj.frozen['items']}

def result_scope(actor,pk,target_key,public=False):
    if not settings.FEEDBACK_ENABLED:raise NotFound()
    obj=m.Cycle.objects.select_related('questionnaire','programme').filter(pk=pk,questionnaire__institution__is_active=True,questionnaire__institution__university__is_active=True).first()
    if not obj or obj.status!='CLOSED' or obj.result_visibility=='HIDDEN':raise NotFound('Feedback results unavailable.')
    if not isinstance(target_key,str) or len(target_key)>80:raise ValidationError('Invalid target.')
    kind=obj.frozen['type'];prefix={'COURSE':'course:','FACULTY':'faculty:','PROGRAMME':'programme:','INSTITUTION':'institution:','EXIT':'exit:','OTHER':'other:'}[kind]
    if not target_key.startswith(prefix) or not target_key[len(prefix):].isdigit():raise NotFound()
    if public:
        from apps.tenancy.models import InstitutionModule
        if obj.result_visibility!='PUBLIC' or not InstitutionModule.objects.filter(institution_id=obj.questionnaire.institution_id,feedback=True).exists():raise NotFound()
        return obj
    if p.cycles(actor,'view_admin_results').filter(pk=pk).exists():return obj
    if not p.enabled(actor,'view_faculty_results') or obj.result_visibility not in ['FACULTY','PUBLIC'] or kind!='FACULTY':raise NotFound()
    assigned=FacultyAssignment.objects.filter(pk=int(target_key[len(prefix):]),employee_id__in=AccountLink.objects.filter(user=actor,employee__employment_status='ACTIVE').values('employee_id')).first()
    if not assigned:raise NotFound()
    offering=assigned.course_offering_section.programme_term_offering
    if offering.academic_term_id!=obj.academic_term_id or (obj.programme_id and offering.programme_id!=obj.programme_id):raise NotFound()
    for grant in p.grants(actor):
        if grant.role!='TEACHER' or not p.valid_limits(grant.record_limits):continue
        section=assigned.course_offering_section;department=section.programme_term_offering.programme.department
        if department.campus.institution_id!=obj.questionnaire.institution_id or grant.membership.institution_id!=obj.questionnaire.institution_id:continue
        if grant.campus_id and grant.campus_id!=department.campus_id:continue
        if grant.department_id and grant.department_id!=department.pk:continue
        if set(grant.record_limits)-{'feedback-cycles','employees','programmes'}:continue
        if any(value not in grant.record_limits[key] for key,value in [('feedback-cycles',obj.pk),('employees',assigned.employee_id),('programmes',section.programme_term_offering.programme_id)] if key in grant.record_limits):continue
        return obj
    raise NotFound()

def aggregates(actor,pk,target_key,public=False):
    obj=result_scope(actor,pk,target_key,public)
    responses=m.Response.objects.filter(feedback_cycle=obj,target_key=target_key)
    count=responses.count();k=obj.minimum_cohort
    base={'cycle_id':str(obj.pk),'cycle_name':obj.cycle_name,'target':target_key,'minimum_cohort':k,'scoring':'Numeric ratings and explicit choice scores normalized to 0-100; multi-choice uses the mean of selected scores. Optional weights normalize by their sum.','generated_at':timezone.now(),'eligible_population':None,'response_rate':None}
    if count<k:return {**base,'suppressed':True,'response_count':None,'questions':[],'weighted_score':None}
    rows=m.ResponseItem.objects.filter(feedback_response__in=responses)
    if rows.count()>50000:raise ValidationError('Result set exceeds the synchronous aggregation limit.')
    values=list(rows.values('pk','questionnaire_item_id','feedback_choice_id','numeric_score','text_response'))
    multi=defaultdict(list)
    for row in m.ResponseItemChoice.objects.filter(feedback_response_item__in=rows).values('feedback_response_item_id','feedback_choice_id'):multi[row['feedback_response_item_id']].append(str(row['feedback_choice_id']))
    grouped=defaultdict(list)
    for row in values:grouped[str(row['questionnaire_item_id'])].append(row)
    results=[];scores=[]
    for item in obj.frozen['items']:
        answers=grouped[item['id']];n=len(answers);kind=item['response_type'];result={'item_id':item['id'],'text':item['text'],'response_type':kind}
        suppress=n<k or 0<count-n<k
        if kind=='TEXT':results.append({**result,'suppressed':suppress,'text_count':None if suppress else n});continue
        normalized=[]
        if kind=='RATING':
            numbers=[row['numeric_score'] for row in answers];bins=Counter(str(x) for x in numbers);suppress=suppress or any(c<k for c in bins.values())
            low=Decimal(item['rating_min']);high=Decimal(item['rating_max'])
            normalized=[(x-low)/(high-low)*100 for x in numbers]
            if not suppress:result.update(average=str(sum(numbers)/n),median=str(median(numbers)),distribution=dict(bins))
        else:
            bins=Counter();choice_scores={c['id']:Decimal(c['score']) for c in item['choices'] if c['score'] is not None}
            for row in answers:
                selected=[str(row['feedback_choice_id'])] if kind=='SINGLE_CHOICE' else multi[row['pk']]
                bins.update(selected)
                if len(choice_scores)==len(item['choices']) and max(choice_scores.values())>min(choice_scores.values()):normalized.append((sum(choice_scores[c] for c in selected)/len(selected)-min(choice_scores.values()))/(max(choice_scores.values())-min(choice_scores.values()))*100)
            suppress=suppress or any(c<k for c in bins.values())
            if not suppress:result['choices']=[{'text':c['text'],'count':bins[c['id']],'percentage':str(Decimal(bins[c['id']])*100/n)} for c in item['choices']]
        result.update(suppressed=suppress,count=None if suppress else n)
        if item['weightage'] is not None and Decimal(item['weightage'])>0:
            scores.append(None if suppress or not normalized else (sum(normalized)/len(normalized),Decimal(item['weightage'])))
        results.append(result)
    weighted=None
    if obj.frozen['weighted'] and scores and all(x is not None for x in scores):weighted=str((sum(score*weight for score,weight in scores)/sum(weight for _,weight in scores)).quantize(Decimal('0.01')))
    return {**base,'suppressed':False,'response_count':count,'questions':results,'weighted_score':weighted}


def faculty_cycles(actor):
    if not p.enabled(actor,'view_faculty_results'):return m.Cycle.objects.none()
    ids=[]
    candidates=m.Cycle.objects.filter(status='CLOSED',result_visibility__in=['FACULTY','PUBLIC'],questionnaire__questionnaire_type='FACULTY',questionnaire__institution_id__in=p.grants(actor).values('membership__institution_id')).select_related('questionnaire')
    if candidates.count()>100:raise ValidationError('Narrow faculty cycle scope.')
    for obj in candidates:
        assignments=FacultyAssignment.objects.filter(employee_id__in=AccountLink.objects.filter(user=actor,employee__employment_status='ACTIVE').values('employee_id'),course_offering_section__programme_term_offering__academic_term_id=obj.academic_term_id)
        for assignment in assignments:
            try:result_scope(actor,obj.pk,'faculty:'+str(assignment.pk));ids.append(obj.pk);break
            except NotFound:continue
    return m.Cycle.objects.filter(pk__in=ids)
