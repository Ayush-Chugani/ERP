from django.conf import settings
from django.db.models import Q,F
from rest_framework.exceptions import NotFound,PermissionDenied
from apps.tenancy.models import ScopeGrant,Membership
from apps.term_registration import models as reg
from apps.people_master.models import AccountLink
from apps.teaching_timetable.models import FacultyAssignment
ADMIN=['INSTITUTION_ADMIN','CAMPUS_ADMIN','DEPARTMENT_ADMIN']
def enabled(actor,action):return bool(settings.ASSESSMENTS_RESULTS_ENABLED and actor.is_authenticated and actor.is_active and (actor.is_superuser or actor.has_perm('assessments_results.'+action+'_assessment')))
def grants(actor):
    return ScopeGrant.objects.filter(membership__user=actor,membership__is_active=True,is_active=True,membership__institution__institutionmodule__assessments_results=True,membership__institution__is_active=True,membership__institution__university__is_active=True).filter(Q(campus__isnull=True)|Q(campus__institution=F('membership__institution'))).filter(Q(department__isnull=True)|Q(department__campus=F('campus')))
def offerings(actor,action='view',day=None,event_id=None,registration_id=None):
    if registration_id and day is None:
        day=reg.StudentCourseRegistration.objects.get(pk=registration_id).term_registration.programme_term_offering.academic_term.end_date
    qs=reg.CourseOffering.objects.filter(programme_term_offering__programme__is_active=True,programme_term_offering__programme__department__is_active=True,programme_term_offering__programme__department__campus__is_active=True,programme_term_offering__programme__department__campus__institution__is_active=True,programme_term_offering__programme__department__campus__institution__university__is_active=True)
    if not enabled(actor,action):return qs.none()
    if actor.is_superuser:return qs
    condition=Q(pk__in=[])
    for g in grants(actor):
        if g.role not in ADMIN+(['TEACHER'] if action in ['view','mark'] else []):continue
        limits=g.record_limits
        if not isinstance(limits,dict) or any(not isinstance(v,list) or any(type(k)is not int or k<1 for k in v) for v in limits.values()):continue
        if any(k in limits for k in ['students','registration-registrations','assessment-events']) and registration_id is None and event_id is None:continue
        if event_id is not None and 'assessment-events' in limits and event_id not in limits['assessment-events']:continue
        if registration_id is not None and 'registration-registrations' in limits and registration_id not in limits['registration-registrations']:continue
        if 'students' in limits:
            if registration_id is None or not reg.StudentCourseRegistration.objects.filter(pk=registration_id,term_registration__enrolment__student_id__in=limits['students']).exists():continue
        part=Q(programme_term_offering__programme__department__campus__institution_id=g.membership.institution_id)
        if g.campus_id:part &= Q(programme_term_offering__programme__department__campus_id=g.campus_id)
        if g.department_id:part &= Q(programme_term_offering__programme__department_id=g.department_id)
        for key,path in {'assessment-offerings':'pk','registration-courses':'pk','registration-offerings':'programme_term_offering_id','programmes':'programme_term_offering__programme_id','courses':'course_id','schemes':'programme_term_offering__curriculum_scheme_id'}.items():
            if key in limits:part &= Q(**{path+'__in':limits[key]})
        if g.role=='TEACHER':
            assignments=FacultyAssignment.objects.filter(employee_id__in=AccountLink.objects.filter(user=actor,employee__employment_status='ACTIVE').values('employee_id'),assignment_status__in=['ACTIVE','COMPLETED'])
            if day:assignments=assignments.filter(start_date__lte=day).filter(Q(end_date__isnull=True)|Q(end_date__gte=day))
            if 'employees' in limits:assignments=assignments.filter(employee_id__in=limits['employees'])
            if registration_id:
                assignments=assignments.filter(course_offering_section_id__in=reg.CourseOfferingSectionStudent.objects.filter(course_registration_id=registration_id,effective_from__lte=day).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=day)).values('course_offering_section_id'))
            part &= Q(pk__in=assignments.values('course_offering_section__course_offering_id'))
        condition |= part
    return qs.filter(condition).distinct()
def offering(actor,pk,action='view',**kw):
    obj=offerings(actor,action,**kw).select_related('programme_term_offering__programme__department__campus','programme_term_offering__academic_term','course').filter(pk=pk).first()
    if obj is None:raise NotFound('Assessment resource unavailable.')
    return obj
def institution(obj):return obj.programme_term_offering.programme.department.campus.institution_id
def institution_access(actor,pk):
    if not enabled(actor,'configure'):raise PermissionDenied()
    if not actor.is_superuser and not grants(actor).filter(role='INSTITUTION_ADMIN',membership__institution_id=pk,record_limits={}).exists():raise NotFound()
def own_student(actor):
    if not settings.ASSESSMENTS_RESULTS_ENABLED or not actor.is_authenticated or not actor.is_active:raise PermissionDenied()
    link=AccountLink.objects.filter(user=actor,student__isnull=False).select_related('student').first()
    if not link or not Membership.objects.filter(user=actor,institution=link.student.institution,is_active=True,institution__institutionmodule__assessments_results=True,institution__is_active=True,institution__university__is_active=True).exists():raise NotFound()
    return link.student_id
