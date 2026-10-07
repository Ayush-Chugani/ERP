from rest_framework.exceptions import ValidationError,NotFound
from apps.term_registration import models as reg
from .. import models as m,permissions as p,services as s

def events(actor):
    # Bound object authorization until per-grant event scopes move fully into SQL.
    base=m.AssessmentEvent.objects.filter(course_offering__in=p.offerings(actor)).select_related('course_offering')
    if base.count()>2000:raise ValidationError('Narrow the scope below 2,000 assessment events.')
    ids=[]
    for obj in base:
        if p.offerings(actor,day=obj.assessment_date,event_id=obj.pk).filter(pk=obj.course_offering_id).exists():ids.append(obj.pk)
    return base.filter(pk__in=ids)
def roster(actor,pk):
    obj=m.AssessmentEvent.objects.select_related('policy').get(pk=pk)
    p.offering(actor,obj.course_offering_id,'view',day=obj.assessment_date,event_id=obj.pk)
    registrations=list(reg.StudentCourseRegistration.objects.filter(pk__in=obj.roster).select_related('term_registration__enrolment__student'))
    marks={row.course_registration_id:row for row in m.StudentAssessmentMark.objects.filter(assessment_event=obj)}
    rows=[]
    for registration in registrations:
        try:s.authorize_registration(actor,obj,registration.pk,'view')
        except NotFound:continue
        student=registration.term_registration.enrolment.student;mark=marks.get(registration.pk)
        rows.append({'course_registration_id':str(registration.pk),'student_number':student.student_number,'student_name':student.display_name,'mark':s.snapshot(mark) if mark else None})
    return {'event':{k:value for k,value in s.snapshot(obj).items() if k!='roster'},'rows':rows}
def scoped_registrations(actor,action='view'):
    base=reg.StudentCourseRegistration.objects.filter(course_offering__in=p.offerings(actor,action)).select_related('course_offering')
    if base.count()>5000:raise ValidationError('Narrow scope below 5,000 course registrations.')
    ids=[row.pk for row in base if p.offerings(actor,action,registration_id=row.pk).filter(pk=row.course_offering_id).exists()]
    return base.filter(pk__in=ids)
def course_results(actor,action='view'):return m.StudentCourseResult.objects.filter(course_registration__in=scoped_registrations(actor,action)).select_related('course_registration__course_offering__course')
def term_results(actor,action='view'):
    base=m.StudentTermResult.objects.filter(term_registration__programme_term_offering_id__in=p.offerings(actor,action).values('programme_term_offering_id'))
    ids=[]
    if base.count()>2000:raise ValidationError('Narrow scope below 2,000 term results.')
    for obj in base:
        try:s.result_offering(actor,obj,action);ids.append(obj.pk)
        except NotFound:continue
    return base.filter(pk__in=ids)
def student_results(actor):
    student=p.own_student(actor);results=[]
    for model,path in [(m.StudentCourseResult,'course_registration__term_registration__enrolment__student_id'),(m.StudentTermResult,'term_registration__enrolment__student_id')]:
        qs=model.objects.filter(**{path:student})
        if qs.count()>1000:raise ValidationError('Student history exceeds 1,000 results; contact the result cell.')
        for obj in qs:
            pub=s.latest(obj)
            if not pub:continue
            data=pub.data
            if isinstance(obj,m.StudentTermResult):
                # A withheld source course must hide a dependent term result immediately.
                ids=data['evidence']['publications'];source=m.Publication.objects.filter(pk__in=ids,resource='studentcourseresult').values_list('record_id',flat=True)
                if m.StudentCourseResult.objects.filter(pk__in=source,is_withheld=True).exists():results.append({'id':str(obj.pk),'resource':'term','result_status':'WITHHELD'});continue
            if obj.is_withheld:results.append({'id':str(obj.pk),'resource':obj._meta.model_name,'result_status':'WITHHELD'});continue
            fields=['attempt_number','internal_marks','external_marks','total_marks','grade_letter','grade_point','credits_earned','credits_registered','sgpa','cgpa','result_status','result_date','published_at']
            if not data['evidence']['rules'].get('show_marks',False):fields=[k for k in fields if k not in ['internal_marks','external_marks','total_marks']]
            item={k:data.get(k) for k in fields if k in data};item.update(id=str(obj.pk),resource=obj._meta.model_name,publication_date=pub.created_at)
            term=obj.course_registration.term_registration if isinstance(obj,m.StudentCourseResult) else obj.term_registration
            item['term_registration_id']=str(term.pk)
            if isinstance(obj,m.StudentCourseResult):item['course_code']=obj.course_registration.course_offering.course.course_code;item['course_title']=obj.course_registration.course_offering.course.course_title
            results.append(item)
    return results
