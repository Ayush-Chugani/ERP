from collections import defaultdict
from datetime import time
from decimal import Decimal
from django.db import transaction
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from drf_spectacular.utils import extend_schema, OpenApiTypes
from . import models as m, serializers as z, services as s
from .api import SchedulingThrottle, safe_cell, TimetableView
from .engine import operational, SchedulingConflict
from .policies import enabled, programmes, grants
from .selectors import read_queryset, read_record, published_occurrences


class HistoryView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(parameters=[z.DateRange], responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        if not enabled(request.user, 'manage_timetable'):
            raise PermissionDenied()
        revision = read_queryset(request.user, 'revisions').filter(pk=pk).first()
        if revision is None:
            raise NotFound()
        query = z.DateRange(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        allowed = set(read_queryset(request.user, 'sessions').filter(revision=revision).values_list('pk', flat=True))
        rows = operational(revision_id=revision.pk, **query.validated_data)
        return Response({'revision_id': str(revision.pk), 'status': revision.status, 'results': [
            {'id': str(row.identity), 'session_id': str(row.session_id),
             'date': str(row.day), 'start_time': str(row.start), 'end_time': str(row.end),
             'course_offering_section_id': str(row.section_id), 'employee_id': str(row.employee_id),
             'room_id': str(row.room_id)} for row in rows if row.session_id in allowed]})


class WorkloadView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(parameters=[z.DateRange], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        if not enabled(request.user, 'manage_timetable'):
            raise PermissionDenied()
        query = z.DateRange(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        start, end = query.validated_data['date_from'], query.validated_data['date_to']
        planned = []
        for obj in read_queryset(request.user, 'assignments').filter(
            start_date__lte=end, assignment_status__in=['PLANNED', 'ACTIVE']).select_related(
            'course_offering_section__programme_term_offering__programme__department'):
            if obj.end_date is not None and obj.end_date < start:
                continue
            offering = obj.course_offering_section.programme_term_offering
            planned.append({'id': str(obj.pk), 'employee_id': str(obj.employee_id),
                'department_id': str(offering.programme.department_id), 'term_id': str(offering.academic_term_id),
                'role': obj.assignment_role, 'weekly_hours': str(obj.workload_hours or 0),
                'start_date': str(obj.start_date), 'end_date': str(obj.end_date) if obj.end_date else None})
        actual = defaultdict(Decimal)
        from datetime import date
        for row in published_occurrences(request.user, start, end):
            first, last = time.fromisoformat(row['start_time']), time.fromisoformat(row['end_time'])
            seconds = last.hour*3600+last.minute*60+last.second-first.hour*3600-first.minute*60-first.second
            week = date.fromisoformat(row['date']).isocalendar()
            actual[(row['employee_id'], week.year, week.week)] += Decimal(seconds)/3600
        return Response({'units': 'hours per ISO week', 'planned_assignments': planned,
            'actual': [{'employee_id': employee, 'year': year, 'week': week,
                'hours': str(hours.quantize(Decimal('0.01')))} for (employee, year, week), hours in sorted(actual.items())]})


class PreviewView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(request=z.Session, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        serializer = z.Session(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                s.write_session(actor=request.user, **serializer.validated_data)
                transaction.set_rollback(True)
            return Response({'valid': True, 'conflicts': [], 'saved': False})
        except (ValidationError, SchedulingConflict) as exc:
            return Response({'valid': False, 'conflicts': exc.detail, 'saved': False})


class WorkloadExportView(WorkloadView):
    @extend_schema(parameters=[z.DateRange], responses={(200, 'text/csv'): OpenApiTypes.STR})
    def get(self, request):
        import csv
        import io
        from django.http import HttpResponse
        if not enabled(request.user, 'export_timetable'):
            raise PermissionDenied()
        data = super().get(request).data
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['type', 'employee_id', 'department_id', 'term_id', 'role', 'year', 'week', 'hours'])
        for row in data['planned_assignments']:
            writer.writerow([safe_cell(value) for value in ['planned', row['employee_id'], row['department_id'], row['term_id'], row['role'], '', '', row['weekly_hours']]])
        for row in data['actual']:
            writer.writerow(['published', row['employee_id'], '', '', '', row['year'], row['week'], row['hours']])
        response = HttpResponse(stream.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="workload.csv"'
        response['Cache-Control'] = 'private, no-store'
        return response


class AvailabilityQuery(z.DateRange):
    kind = serializers.ChoiceField(choices=['room', 'faculty'])
    resource_id = serializers.IntegerField(min_value=1)


class AvailabilityView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(parameters=[AvailabilityQuery], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from django.db.models import Q
        from apps.organization.models import Room
        from apps.people_master.models import Employee, EmployeeAssignment
        actor = request.user
        if not enabled(actor, 'manage_timetable'):
            raise PermissionDenied()
        query = AvailabilityQuery(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        data = query.validated_data
        start, end, pk = data['date_from'], data['date_to'], data['resource_id']
        allowed = programmes(actor)
        resource = 'rooms' if data['kind'] == 'room' else 'employees'
        if resource == 'rooms':
            obj = Room.objects.filter(pk=pk, building__campus_id__in=allowed.values('department__campus_id')).select_related('building__campus').first()
            institution_id = obj.building.campus.institution_id if obj else None
        else:
            employment = EmployeeAssignment.objects.filter(employee_id=pk,
                department_id__in=allowed.values('department_id'), start_date__lte=end).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=start))
            obj = Employee.objects.filter(pk=pk, pk__in=employment.values('employee_id')).first()
            institution_id = obj.institution_id if obj else None
        if obj is None:
            raise NotFound()
        authorized = actor.is_superuser
        for grant in grants(actor).filter(membership__institution_id=institution_id,
            role__in=['INSTITUTION_ADMIN', 'CAMPUS_ADMIN', 'DEPARTMENT_ADMIN']):
            limits = grant.record_limits
            if not isinstance(limits, dict) or (resource in limits and (not isinstance(limits[resource], list) or pk not in limits[resource])):
                continue
            if resource == 'rooms':
                if grant.campus_id and obj.building.campus_id != grant.campus_id:
                    continue
            else:
                scoped = employment
                if grant.campus_id:
                    scoped = scoped.filter(campus_id=grant.campus_id)
                if grant.department_id:
                    scoped = scoped.filter(department_id=grant.department_id)
                if not scoped.exists():
                    continue
            authorized = True
        if not authorized:
            raise NotFound()
        field = 'room_id' if resource == 'rooms' else 'employee_id'
        evidence = m.ResourceAvailability.objects.filter(**{field: pk}, institution_id=institution_id,
            effective_from__lte=end, effective_to__gte=start).order_by('day_of_week', 'start_time')
        busy = [row for row in operational(date_from=start, date_to=end) if getattr(row, field) == pk]
        return Response({'windows': [{'weekday': row.day_of_week, 'from': str(row.effective_from),
            'to': str(row.effective_to), 'start': str(row.start_time), 'end': str(row.end_time)} for row in evidence],
            'busy': [{'date': str(row.day), 'start': str(row.start), 'end': str(row.end)} for row in busy],
            'note': 'Availability evidence and published occupancy are shown separately. Scheduling revalidates both.'})
