"""Current scope and dated faculty authority; no trust in client ownership IDs."""
from django.conf import settings
from django.db.models import Q,F
from rest_framework.exceptions import NotFound,PermissionDenied
from apps.tenancy.models import ScopeGrant,Membership
from apps.people_master.models import AccountLink
from apps.term_registration.models import CourseOfferingSection
from apps.teaching_timetable.models import FacultyAssignment

ADMIN_ROLES=['INSTITUTION_ADMIN','CAMPUS_ADMIN','DEPARTMENT_ADMIN']

def enabled(actor,action):
    return bool(getattr(settings,'ATTENDANCE_ENABLED',False) and actor.is_authenticated and actor.is_active and
        (actor.is_superuser or actor.has_perm('attendance_lesson_plan.'+action)))

def grants(actor):
    return ScopeGrant.objects.filter(membership__user=actor,membership__is_active=True,is_active=True,
        membership__institution__institutionmodule__attendance_lesson_plan=True,
        membership__institution__is_active=True,membership__institution__university__is_active=True).filter(
        Q(campus__isnull=True)|Q(campus__institution=F('membership__institution'))).filter(
        Q(department__isnull=True)|Q(department__campus=F('campus')))

def sections(actor,action='view_attendance',day=None,session_id=None,employee_id=None,room_id=None,grant_rows=None):
    qs=CourseOfferingSection.objects.filter(programme_term_offering__programme__is_active=True,
        programme_term_offering__programme__department__is_active=True,
        programme_term_offering__programme__department__campus__is_active=True,
        programme_term_offering__programme__department__campus__institution__is_active=True,
        programme_term_offering__programme__department__campus__institution__university__is_active=True)
    if not enabled(actor,action): return qs.none()
    if actor.is_superuser:return qs
    condition=Q(pk__in=[])
    employees=AccountLink.objects.filter(user=actor,employee__employment_status='ACTIVE').values('employee_id')
    assignments=FacultyAssignment.objects.filter(employee_id__in=employees,assignment_status__in=['ACTIVE','COMPLETED'])
    if day: assignments=assignments.filter(start_date__lte=day).filter(Q(end_date__isnull=True)|Q(end_date__gte=day))
    administrative=action in ['configure_attendance','review_attendance','reopen_attendance','exceptional_attendance']
    for grant in (grants(actor) if grant_rows is None else grant_rows):
        if grant.role not in ADMIN_ROLES+([] if administrative else ['TEACHER']): continue
        limits=grant.record_limits
        if not isinstance(limits,dict) or any(not isinstance(ids,list) or any(type(pk)is not int or pk<1 for pk in ids) for ids in limits.values()):continue
        # A full register cannot be delegated through a partial student allowlist.
        if 'students' in limits:continue
        if session_id is not None and 'attendance-sessions' in limits and session_id not in limits['attendance-sessions']:continue
        if employee_id is not None and 'employees' in limits and employee_id not in limits['employees']:continue
        if room_id is not None and 'rooms' in limits and room_id not in limits['rooms']:continue
        part=Q(programme_term_offering__programme__department__campus__institution_id=grant.membership.institution_id)
        if grant.campus_id:part &= Q(programme_term_offering__programme__department__campus_id=grant.campus_id)
        if grant.department_id:part &= Q(programme_term_offering__programme__department_id=grant.department_id)
        paths={'programmes':'programme_term_offering__programme_id','courses':'course_offering__course_id','schemes':'programme_term_offering__curriculum_scheme_id','attendance-sections':'pk','registration-mappings':'pk','registration-offerings':'programme_term_offering_id'}
        for key,path in paths.items():
            if key in limits:part &= Q(**{path+'__in':limits[key]})
        if grant.role=='TEACHER':
            dated=assignments.filter(employee_id=employee_id) if employee_id is not None else assignments
            part &= Q(pk__in=dated.values('course_offering_section_id'))
        condition |= part
    return qs.filter(condition).distinct()

def require_section(actor,pk,action,day=None):
    obj=sections(actor,action,day).select_related('programme_term_offering__programme__department__campus','programme_term_offering__academic_term','course_offering__course').filter(pk=pk).first()
    if obj is None:raise NotFound('Attendance resource unavailable.')
    return obj

def require_session(actor,obj,action):
    if not sections(actor,action,obj.session_date,obj.pk or 0,obj.faculty_assignment.employee_id,obj.room_id).filter(pk=obj.course_offering_section_id).exists():
        raise NotFound('Attendance resource unavailable.')

def own_student(actor):
    if not getattr(settings,'ATTENDANCE_ENABLED',False) or not actor.is_authenticated or not actor.is_active:raise PermissionDenied()
    link=AccountLink.objects.filter(user=actor,student__isnull=False).first()
    if not link or not Membership.objects.filter(user=actor,institution=link.student.institution,is_active=True,
        institution__institutionmodule__attendance_lesson_plan=True,institution__is_active=True,institution__university__is_active=True).exists():raise NotFound()
    return link.student_id


def scoped_sessions(actor,action='view_attendance'):
    from .models import ClassSession
    from django.db.models import Exists,OuterRef
    base=ClassSession.objects.filter(course_offering_section__in=sections(actor,action))
    if actor.is_superuser:return base
    condition=Q(pk__in=[])
    employees=AccountLink.objects.filter(user=actor,employee__employment_status='ACTIVE').values('employee_id')
    dated=FacultyAssignment.objects.filter(pk=OuterRef('faculty_assignment_id'),employee_id__in=employees,start_date__lte=OuterRef('session_date'),assignment_status__in=['ACTIVE','COMPLETED']).filter(Q(end_date__isnull=True)|Q(end_date__gte=OuterRef('session_date')))
    base=base.alias(own_assignment=Exists(dated))
    for grant in grants(actor):
        limits=grant.record_limits
        if not isinstance(limits,dict) or any(not isinstance(ids,list) or any(type(pk)is not int or pk<1 for pk in ids) for ids in limits.values()):continue
        part=Q(course_offering_section__in=sections(actor,action,grant_rows=[grant]))
        for key,path in {'attendance-sessions':'pk','employees':'faculty_assignment__employee_id','rooms':'room_id'}.items():
            if key in limits:part &= Q(**{path+'__in':limits[key]})
        if grant.role=='TEACHER':part &= Q(own_assignment=True)
        condition |= part
    return base.filter(condition)
