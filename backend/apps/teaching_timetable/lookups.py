from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiTypes
from apps.core.pagination import BoundedPagination
from apps.term_registration import models as reg
from apps.organization.models import Institution, Room
from apps.people_master.models import Employee, EmployeeAssignment
from apps.academic_calendar.models import TimeSlot
from .policies import programmes, enabled, grants
from .models import SchedulingPolicy
from .api import SchedulingThrottle, TimetableView


class LookupView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, resource):
        actor = request.user
        if not enabled(actor, 'manage_timetable'):
            raise PermissionDenied()
        allowed = programmes(actor)
        campuses = allowed.values('department__campus_id')
        institutions = allowed.values('department__campus__institution_id')
        if resource == 'offerings':
            qs = reg.ProgrammeTermOffering.objects.filter(programme__in=allowed)
            label = lambda obj: f'{obj.programme.programme_name} / {obj.academic_term.term_name}'
            related = ('programme', 'academic_term')
        elif resource == 'sections':
            qs = reg.CourseOfferingSection.objects.filter(programme_term_offering__programme__in=allowed)
            label = lambda obj: f'{obj.course_offering.course.course_code} / {obj.class_section.section_code} / {obj.session_type}'
            related = ('course_offering__course', 'class_section')
        elif resource == 'rooms':
            qs = Room.objects.filter(building__campus_id__in=campuses, is_active=True)
            label, related = lambda obj: obj.room_code, ()
        elif resource == 'employees':
            qs = Employee.objects.filter(pk__in=EmployeeAssignment.objects.filter(
                department_id__in=allowed.values('department_id')).values('employee_id'), employment_status='ACTIVE')
            label, related = lambda obj: obj.display_name, ()
        elif resource == 'time-slots':
            qs = TimeSlot.objects.filter(campus_id__in=campuses, is_active=True, is_break=False)
            label, related = lambda obj: f'{obj.slot_code} ({obj.start_time:%H:%M}–{obj.end_time:%H:%M})', ()
        elif resource == 'institutions':
            qs = Institution.objects.filter(pk__in=institutions)
            label, related = lambda obj: obj.institution_name, ()
        elif resource == 'policies':
            qs = SchedulingPolicy.objects.filter(institution_id__in=institutions)
            label, related = lambda obj: f'{obj.institution.institution_name}: {obj.weekly_limit} h/week (version {obj.version})', ('institution',)
        else:
            raise NotFound()
        if not actor.is_superuser and resource in ('employees', 'rooms', 'time-slots'):
            # Apply per-resource limits within the corresponding grant's institution/campus.
            paths = {'employees': ('institution_id', None), 'rooms': ('building__campus__institution_id', 'building__campus_id'), 'time-slots': ('campus__institution_id', 'campus_id')}
            institution_path, campus_path = paths[resource]
            condition = Q(pk__in=[])
            for grant in grants(actor).filter(role__in=['INSTITUTION_ADMIN', 'CAMPUS_ADMIN', 'DEPARTMENT_ADMIN']):
                part = Q(**{institution_path: grant.membership.institution_id})
                if campus_path and grant.campus_id:
                    part &= Q(**{campus_path: grant.campus_id})
                if not isinstance(grant.record_limits, dict):
                    continue
                ids = grant.record_limits.get(resource)
                if ids is not None:
                    if not isinstance(ids, list):
                        continue
                    part &= Q(pk__in=ids)
                condition |= part
            qs = qs.filter(condition)
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(qs.select_related(*related).order_by('pk'), request)
        result = []
        for obj in page:
            row = {'id': str(obj.pk), 'label': label(obj)}
            if resource == 'sections':
                row['offering_id'] = str(obj.programme_term_offering_id)
            if resource == 'policies':
                row.update(institution_id=str(obj.institution_id), version=obj.version,
                    weekly_limit=str(obj.weekly_limit), require_competency=obj.require_competency,
                    max_sessions=obj.max_sessions, max_solver_jobs=obj.max_solver_jobs)
            result.append(row)
        return paginator.get_paginated_response(result)
