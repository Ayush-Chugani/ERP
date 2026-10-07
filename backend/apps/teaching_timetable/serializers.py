from decimal import Decimal
from rest_framework import serializers as z
from . import models as m


class Strict(z.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise z.ValidationError({'non_field_errors': ['Unsupported fields.']})
        return super().to_internal_value(data)


class Reason(Strict):
    reason = z.CharField(max_length=500)


class Assignment(Reason):
    course_offering_section_id = z.IntegerField(min_value=1)
    employee_id = z.IntegerField(min_value=1)
    assignment_role = z.ChoiceField(choices=m.AssignmentRole.choices)
    workload_hours = z.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal('0.01'), allow_null=True)
    start_date = z.DateField()
    end_date = z.DateField(allow_null=True)
    cross_department_authorized = z.BooleanField(default=False)


class TimetableTransition(Reason):
    pk = z.IntegerField(min_value=1)
    expected_version = z.IntegerField(min_value=1)
    target = z.CharField(max_length=12)


class Revision(Reason):
    offering_id = z.IntegerField(min_value=1)
    name = z.CharField(max_length=150)


class SessionValues(Strict):
    course_offering_section_id = z.IntegerField(min_value=1)
    faculty_assignment_id = z.IntegerField(min_value=1, allow_null=True)
    room_id = z.IntegerField(min_value=1, allow_null=True)
    time_slot_id = z.IntegerField(min_value=1)
    day_of_week = z.IntegerField(min_value=1, max_value=7)
    effective_from = z.DateField()
    effective_to = z.DateField()


class Session(Reason):
    revision_id = z.IntegerField(min_value=1)
    expected_version = z.IntegerField(min_value=1)
    pk = z.IntegerField(min_value=1, required=False)
    values = SessionValues()


class RemoveSession(Reason):
    revision_id = z.IntegerField(min_value=1)
    expected_version = z.IntegerField(min_value=1)
    pk = z.IntegerField(min_value=1)


class Availability(Reason):
    room_id = z.IntegerField(min_value=1, allow_null=True, required=False)
    employee_id = z.IntegerField(min_value=1, allow_null=True, required=False)
    day_of_week = z.IntegerField(min_value=1, max_value=7)
    effective_from = z.DateField()
    effective_to = z.DateField()
    start_time = z.TimeField()
    end_time = z.TimeField()


class ExceptionValues(Strict):
    kind = z.ChoiceField(choices=['CANCEL', 'MOVE', 'SUBSTITUTE'])
    date = z.DateField()
    start_time = z.TimeField()
    end_time = z.TimeField()
    room_id = z.IntegerField(min_value=1)
    faculty_assignment_id = z.IntegerField(min_value=1)


class ExceptionCommand(Reason):
    occurrence_id = z.IntegerField(min_value=1)
    expected_sequence = z.IntegerField(min_value=0)
    values = ExceptionValues()


class PolicyValues(Strict):
    weekly_limit = z.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal('0.01'))
    require_competency = z.BooleanField(default=True)
    max_sessions = z.IntegerField(min_value=1, max_value=500, default=250)
    max_solver_jobs = z.IntegerField(min_value=1, max_value=10, default=2)


class Policy(Reason):
    institution_id = z.IntegerField(min_value=1)
    expected_version = z.IntegerField(min_value=1, required=False)
    values = PolicyValues()


class QueueJob(Reason):
    revision_id = z.IntegerField(min_value=1)
    expected_version = z.IntegerField(min_value=1)
    seed = z.IntegerField(min_value=0, max_value=2147483647, default=0)
    choices = z.ListField(child=z.ListField(child=SessionValues(), min_length=1, max_length=20), min_length=1, max_length=100)


class JobAction(Reason):
    pk = z.IntegerField(min_value=1)
    expected_version = z.IntegerField(min_value=1)


class AcceptCandidate(JobAction):
    candidate_index = z.IntegerField(min_value=0, max_value=2, default=0)


class OverrideValues(Strict):
    employee_id = z.IntegerField(min_value=1)
    effective_from = z.DateField()
    effective_to = z.DateField()
    weekly_limit = z.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal('0.01'))


class WorkloadOverride(Reason):
    values = OverrideValues()


class AmendValues(Strict):
    workload_hours = z.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal('0.01'))
    start_date = z.DateField()
    end_date = z.DateField(allow_null=True)


class AmendAssignment(JobAction):
    values = AmendValues()


class BulkAssignments(Reason):
    rows = Assignment(many=True)
    dry_run = z.BooleanField(default=True)


class DateRange(Strict):
    date_from = z.DateField()
    date_to = z.DateField()

    def validate(self, value):
        if not 0 <= (value['date_to'] - value['date_from']).days <= 92:
            raise z.ValidationError('Select a date range of at most 93 days.')
        return value


class CommandResult(z.Serializer):
    id = z.CharField()
    version = z.IntegerField(allow_null=True)
    resource = z.CharField()
