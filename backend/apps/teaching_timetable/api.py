import csv
import io
import json
from django.http import HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiTypes
from apps.core.pagination import BoundedPagination
from . import serializers as z, services as s, solver
from .policies import enabled, programmes, require_programme, require_institution
from .selectors import READS, read_queryset, read_record, published_occurrences


class SchedulingThrottle(UserRateThrottle):
    scope = 'timetable'
    rate = '120/min'


class TimetableView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        from django.utils.cache import patch_vary_headers
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        patch_vary_headers(response, ['Authorization', 'Cookie'])
        return response


def values_call(fn):
    def invoke(*, actor, **data):
        reason = data.pop('reason')
        return fn(actor=actor, values=data, reason=reason)
    return invoke


COMMANDS = {
    'amend-assignment': (z.AmendAssignment, s.amend_assignment, 'manage_timetable'),
    'workload-override': (z.WorkloadOverride, s.approve_workload_override, 'override_workload'),
    'configure-policy': (z.Policy, s.configure_policy, 'configure_timetable'),
    'create-assignment': (z.Assignment, values_call(s.create_assignment), 'manage_timetable'),
    'transition-assignment': (z.TimetableTransition, s.transition_assignment, 'manage_timetable'),
    'create-revision': (z.Revision, s.create_revision, 'manage_timetable'),
    'save-session': (z.Session, s.write_session, 'manage_timetable'),
    'remove-session': (z.RemoveSession, s.remove_session, 'manage_timetable'),
    'transition-revision': (z.TimetableTransition, s.transition_revision, 'manage_timetable'),
    'attest-availability': (z.Availability, values_call(s.attest_availability), 'manage_timetable'),
    'exception': (z.ExceptionCommand, s.add_exception, 'change_occurrence'),
    'queue-job': (z.QueueJob, solver.queue_job, 'manage_timetable'),
    'cancel-job': (z.JobAction, solver.cancel_job, 'manage_timetable'),
    'accept-job': (z.AcceptCandidate, solver.accept_job, 'manage_timetable'),
}


def authorize(actor, operation, data):
    """Recheck scopes before returning an idempotent receipt, too."""
    from . import models as m
    from apps.term_registration.models import ProgrammeTermOffering, CourseOfferingSection
    action = COMMANDS[operation][2]
    if operation == 'transition-revision':
        action = 'publish_timetable' if data['target'] in ('PUBLISHED', 'WITHDRAWN') else 'approve_timetable' if data['target'] == 'APPROVED' else 'manage_timetable'
    if not enabled(actor, action):
        raise PermissionDenied('Scheduling authority unavailable.')
    if operation == 'workload-override':
        from apps.people_master.models import Employee
        employee = Employee.objects.filter(pk=data['values']['employee_id']).first()
        if employee is None:
            raise NotFound()
        require_institution(actor, employee.institution_id, action)
    if 'institution_id' in data:
        require_institution(actor, data['institution_id'], action)
    elif 'revision_id' in data:
        s.revision_for(actor, data['revision_id'], action)
    elif operation == 'transition-revision':
        s.revision_for(actor, data['pk'], action)
    elif operation in ('cancel-job', 'accept-job'):
        obj = m.SolverJob.objects.filter(pk=data['pk'], revision__plan__programme_term_offering__programme__in=programmes(actor)).first()
        if obj is None:
            raise NotFound()
    elif operation == 'exception':
        if not m.PublishedOccurrence.objects.filter(pk=data['occurrence_id'], revision__plan__programme_term_offering__programme__in=programmes(actor, action)).exists():
            raise NotFound()
    elif operation in ('transition-assignment', 'amend-assignment'):
        if not read_queryset(actor, 'assignments').filter(pk=data['pk']).exists():
            raise NotFound()
    elif operation == 'create-assignment':
        if not CourseOfferingSection.objects.filter(pk=data['course_offering_section_id'], programme_term_offering__programme__in=programmes(actor)).exists():
            raise NotFound()
    elif operation == 'create-revision':
        if not ProgrammeTermOffering.objects.filter(pk=data['offering_id'], programme__in=programmes(actor)).exists():
            raise NotFound()
    elif operation == 'attest-availability':
        from apps.organization.models import Room
        from apps.people_master.models import Employee
        try:
            institution_id = Room.objects.get(pk=data['room_id']).building.campus.institution_id if data.get('room_id') else Employee.objects.get(pk=data.get('employee_id')).institution_id
        except (Room.DoesNotExist, Employee.DoesNotExist):
            raise NotFound() from None
        require_institution(actor, institution_id, action)


class CommandView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=z.CommandResult,
        description='Explicit command endpoint. Requires Idempotency-Key; command schemas and version fields are documented in M8_IMPLEMENTATION.md.')
    def post(self, request, operation):
        if operation not in COMMANDS:
            raise NotFound()
        serializer_class, execute, _ = COMMANDS[operation]
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Queue snapshots are JSON values, independent of serializer date objects.
        if operation == 'queue-job':
            data['choices'] = json.loads(json.dumps(data['choices'], cls=DjangoJSONEncoder))
        @s.command
        def perform(*, actor):
            authorize(actor, operation, data)
            def call(current_actor):
                obj = execute(actor=current_actor, **data)
                return {'id': str(obj.pk), 'version': getattr(obj, 'version', None), 'resource': obj._meta.model_name}
            return s.idempotent(actor=actor, key=request.headers.get('Idempotency-Key', ''),
                operation=operation, payload=data, execute=call)
        return Response(perform(actor=request.user))


def command_view(operation):
    """Expose each command's exact request schema in OpenAPI."""
    serializer, _, _ = COMMANDS[operation]
    class ExplicitCommandView(CommandView):
        @extend_schema(request=serializer, responses=z.CommandResult,
            operation_id='timetable_' + operation.replace('-', '_'))
        def post(self, request):
            return super().post(request, operation)
    return ExplicitCommandView.as_view()


class RecordsView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, resource):
        if resource not in READS:
            raise NotFound()
        if not enabled(request.user, 'manage_timetable'):
            raise PermissionDenied()
        qs = read_queryset(request.user, resource)
        for field in ('revision_id', 'employee_id', 'course_offering_section_id'):
            if field in request.query_params and field in READS[resource][2]:
                value = request.query_params[field]
                if not value.isdigit():
                    raise ValidationError('Filter identifiers must be positive integers.')
                qs = qs.filter(**{field: value})
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response([read_record(obj, READS[resource][2]) for obj in page])


class OccurrencesView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(parameters=[z.DateRange], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        if not enabled(request.user, 'view_schedule'):
            raise PermissionDenied()
        serializer = z.DateRange(data=request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        rows = published_occurrences(request.user, **serializer.validated_data)
        response = Response({'results': rows})
        response['Cache-Control'] = 'private, no-store'
        return response


class ExportView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(parameters=[z.DateRange], responses={(200, 'text/csv'): OpenApiTypes.STR})
    def get(self, request):
        if not enabled(request.user, 'export_timetable') or not enabled(request.user, 'view_schedule'):
            raise PermissionDenied()
        serializer = z.DateRange(data=request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        rows = published_occurrences(request.user, **serializer.validated_data)
        stream = io.StringIO(newline='')
        columns = ['id', 'date', 'start_time', 'end_time', 'course_offering_section_id', 'room_id', 'employee_id']
        writer = csv.writer(stream)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([safe_cell(row[name]) for name in columns])
        response = HttpResponse(stream.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="timetable.csv"'
        response['Cache-Control'] = 'private, no-store'
        return response


def safe_cell(value):
    value = str(value or '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


class BulkView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(request=z.BulkAssignments, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        serializer = z.BulkAssignments(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        rows = [{k: v for k, v in row.items() if k != 'reason'} for row in data['rows']]
        @s.command
        def perform(*, actor):
            for row in rows:
                authorize(actor, 'create-assignment', row)
            return s.idempotent(actor=actor, key=request.headers.get('Idempotency-Key', ''),
                operation='bulk-assignments', payload=data,
                execute=lambda current: s.bulk_assignments(actor=current, rows=rows,
                    dry_run=data['dry_run'], reason=data['reason']))
        return Response(perform(actor=request.user))


class ImportView(TimetableView):
    throttle_classes = [SchedulingThrottle]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT,
        description='Mapped allocation CSV in csv_text, reason, dry_run (default true). Maximum 50 rows and 250 KB. Requires Idempotency-Key.')
    def post(self, request):
        from .importing import parse_allocations
        if not enabled(request.user, 'manage_timetable'):
            raise PermissionDenied()
        data = request.data
        if not isinstance(data, dict) or set(data) - {'csv_text', 'reason', 'dry_run'}:
            raise ValidationError('Unsupported import fields.')
        if not isinstance(data.get('csv_text'), str) or type(data.get('dry_run', True)) is not bool:
            raise ValidationError('Supply csv_text and a boolean dry_run flag.')
        s.reason_required(data.get('reason'))
        rows, quarantine = parse_allocations(data['csv_text'], data['reason'])
        if quarantine:
            return Response({'dry_run': True, 'results': [], 'conflicts': quarantine})
        values = [row['values'] for row in rows]
        @s.command
        def perform(*, actor):
            for row in values:
                authorize(actor, 'create-assignment', row)
            return s.idempotent(actor=actor, key=request.headers.get('Idempotency-Key', ''),
                operation='import-allocations', payload=data,
                execute=lambda current: s.bulk_assignments(actor=current, rows=values,
                    dry_run=data.get('dry_run', True), reason=data['reason']))
        return Response(perform(actor=request.user))
