"""M8 domain records. Writes go through command services, including publication."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from apps.core.models import AppendOnlyQuerySet
from apps.people_master.fields import UnsignedBigAutoField


def parent(model, **kwargs):
    return models.ForeignKey(model, on_delete=models.PROTECT, related_name='+', **kwargs)


class Record(models.Model):
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = parent(settings.AUTH_USER_MODEL)
    updated_by = parent(settings.AUTH_USER_MODEL)

    class Meta:
        abstract = True
        default_permissions = ('view',)


class Immutable(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True
        default_permissions = ('view',)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Published evidence is immutable.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Published evidence is immutable.')


class SchedulingPolicy(Record):
    institution = models.OneToOneField('organization.Institution', on_delete=models.PROTECT)
    weekly_limit = models.DecimalField(max_digits=6, decimal_places=2)
    require_competency = models.BooleanField(default=True)
    max_sessions = models.PositiveSmallIntegerField(default=250)
    max_solver_jobs = models.PositiveSmallIntegerField(default=2)

    class Meta:
        db_table = 'platform_m8_policy'
        constraints = [
            models.CheckConstraint(condition=Q(weekly_limit__gt=0), name='chk_m8_weekly_limit'),
            models.CheckConstraint(condition=Q(max_sessions__gte=1, max_sessions__lte=500), name='chk_m8_session_limit'),
            models.CheckConstraint(condition=Q(max_solver_jobs__gte=1, max_solver_jobs__lte=10), name='chk_m8_job_limit'),
        ]
        permissions = [('configure_timetable', 'Configure scheduling policy')]


class AssignmentRole(models.TextChoices):
    PRIMARY_INSTRUCTOR = 'PRIMARY_INSTRUCTOR'
    CO_INSTRUCTOR = 'CO_INSTRUCTOR'
    LAB_INSTRUCTOR = 'LAB_INSTRUCTOR'
    TUTOR = 'TUTOR'
    COORDINATOR = 'COORDINATOR'
    OTHER = 'OTHER'


class AssignmentStatus(models.TextChoices):
    PLANNED = 'PLANNED'
    ACTIVE = 'ACTIVE'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class FacultyAssignment(Record):
    faculty_assignment_id = UnsignedBigAutoField(primary_key=True)
    course_offering_section = parent('term_registration.CourseOfferingSection')
    employee = parent('people_master.Employee')
    assignment_role = models.CharField(max_length=18, choices=AssignmentRole.choices)
    workload_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    assignment_status = models.CharField(max_length=9, choices=AssignmentStatus.choices, default='PLANNED')
    cross_department_authorized = models.BooleanField(default=False)

    class Meta:
        db_table = 'faculty_course_assignment'
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(fields=['course_offering_section', 'employee', 'assignment_role', 'start_date'], name='uq_faculty_course_assignment'),
            models.UniqueConstraint(fields=['faculty_assignment_id', 'course_offering_section'], name='uq_m8_faculty_section'),
            models.CheckConstraint(condition=Q(end_date__isnull=True) | Q(end_date__gte=F('start_date')), name='chk_m8_assignment_dates'),
            models.CheckConstraint(condition=Q(workload_hours__isnull=True) | Q(workload_hours__gt=0), name='chk_m8_workload'),
            models.CheckConstraint(condition=Q(assignment_role__in=AssignmentRole.values), name='chk_m8_assignment_role'),
            models.CheckConstraint(condition=Q(assignment_status__in=AssignmentStatus.values), name='chk_m8_assignment_status'),
        ]
        indexes = [models.Index(fields=['employee', 'assignment_status', 'start_date', 'end_date'], name='ix_m8_employee_dates')]
        permissions = [('manage_timetable', 'Plan faculty and timetable'), ('override_workload', 'Override workload with reason'), ('cross_department_teaching', 'Authorize cross-department teaching')]

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'Must not precede start date.'})


class TimetablePlan(Record):
    programme_term_offering = models.OneToOneField('term_registration.ProgrammeTermOffering', on_delete=models.PROTECT)
    name = models.CharField(max_length=150)

    class Meta:
        db_table = 'platform_m8_plan'


class RevisionStatus(models.TextChoices):
    DRAFT = 'DRAFT'
    REVIEW = 'REVIEW'
    APPROVED = 'APPROVED'
    PUBLISHED = 'PUBLISHED'
    SUPERSEDED = 'SUPERSEDED'
    WITHDRAWN = 'WITHDRAWN'
    ARCHIVED = 'ARCHIVED'


class TimetableRevision(Record):
    plan = parent(TimetablePlan)
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=RevisionStatus.choices, default='DRAFT')

    class Meta:
        db_table = 'platform_m8_revision'
        ordering = ['plan_id', 'number']
        constraints = [
            models.UniqueConstraint(fields=['plan', 'number'], name='uq_m8_revision_number'),
            models.CheckConstraint(condition=Q(status__in=RevisionStatus.values), name='chk_m8_revision_status'),
        ]
        permissions = [('approve_timetable', 'Approve timetable revisions'), ('publish_timetable', 'Publish or withdraw timetables'), ('view_schedule', 'View scoped published schedules'), ('export_timetable', 'Export scoped timetables')]


class TimetableSession(Record):
    timetable_session_id = UnsignedBigAutoField(primary_key=True)
    revision = parent(TimetableRevision)
    course_offering_section = parent('term_registration.CourseOfferingSection')
    faculty_assignment = parent(FacultyAssignment, null=True, blank=True)
    day_of_week = models.PositiveSmallIntegerField()
    time_slot = parent('academic_calendar.TimeSlot')
    room = parent('organization.Room', null=True, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField()

    class Meta:
        db_table = 'timetable_session'
        ordering = ['day_of_week', 'time_slot_id', 'pk']
        constraints = [
            models.CheckConstraint(condition=Q(day_of_week__gte=1, day_of_week__lte=7), name='chk_day_of_week'),
            models.UniqueConstraint(fields=['timetable_session_id','course_offering_section'],name='uq_m9_timetable_section'),
            models.CheckConstraint(condition=Q(effective_to__gte=F('effective_from')), name='chk_m8_session_dates'),
        ]
        indexes = [
            models.Index(fields=['room', 'day_of_week', 'effective_from', 'effective_to'], name='ix_m8_room_interval'),
            models.Index(fields=['faculty_assignment', 'day_of_week', 'effective_from'], name='ix_m8_faculty_interval'),
            models.Index(fields=['revision', 'course_offering_section'], name='ix_m8_revision_section'),
        ]

    def clean(self):
        if self.effective_to < self.effective_from:
            raise ValidationError({'effective_to': 'Must not precede start date.'})
        if self.faculty_assignment_id and self.faculty_assignment.course_offering_section_id != self.course_offering_section_id:
            raise ValidationError({'faculty_assignment': 'Assignment belongs to another section.'})


class PublishedOccurrence(Immutable):
    revision = parent(TimetableRevision)
    session = parent(TimetableSession)
    course_offering_section = parent('term_registration.CourseOfferingSection')
    class_section = parent('term_registration.ClassSection')
    class_batch = parent('term_registration.ClassBatch', null=True, blank=True)
    employee = parent('people_master.Employee')
    room = parent('organization.Room')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    # Roster snapshot makes historical cohort occupancy independent of later roster edits.
    student_ids = models.JSONField(default=list)

    class Meta:
        db_table = 'platform_m8_occurrence'
        constraints = [
            models.UniqueConstraint(fields=['session', 'date'], name='uq_m8_occurrence'),
            models.UniqueConstraint(fields=['id','course_offering_section'],name='uq_m9_occurrence_section'),
            models.CheckConstraint(condition=Q(end_time__gt=F('start_time')), name='chk_m8_occurrence_clock'),
        ]
        indexes = [models.Index(fields=['date', 'room', 'start_time'], name='ix_m8_occurrence_room'), models.Index(fields=['date', 'employee', 'start_time'], name='ix_m8_occurrence_faculty')]


class OccurrenceException(Immutable):
    occurrence = parent(PublishedOccurrence)
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=[('CANCEL', 'Cancel'), ('MOVE', 'Move'), ('SUBSTITUTE', 'Substitute')])
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = parent('organization.Room')
    faculty_assignment = parent(FacultyAssignment)
    reason = models.CharField(max_length=500)
    actor = parent(settings.AUTH_USER_MODEL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_m8_exception'
        constraints = [
            models.UniqueConstraint(fields=['occurrence', 'sequence'], name='uq_m8_exception_sequence'),
            models.CheckConstraint(condition=Q(kind__in=['CANCEL', 'MOVE', 'SUBSTITUTE']), name='chk_m8_exception_kind'),
            models.CheckConstraint(condition=Q(end_time__gt=F('start_time')), name='chk_m8_exception_clock'),
        ]
        permissions = [('change_occurrence', 'Approve dated timetable exceptions')]


class ResourceAvailability(Record):
    """Positive availability attestation, not a replacement room/staff master."""
    institution = parent('organization.Institution')
    room = parent('organization.Room', null=True, blank=True)
    employee = parent('people_master.Employee', null=True, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField()
    day_of_week = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=500)

    class Meta:
        db_table = 'platform_m8_availability'
        constraints = [
            models.CheckConstraint(condition=Q(room__isnull=False, employee__isnull=True) | Q(room__isnull=True, employee__isnull=False), name='chk_m8_availability_resource'),
            models.CheckConstraint(condition=Q(effective_to__gte=F('effective_from')), name='chk_m8_availability_dates'),
            models.CheckConstraint(condition=Q(end_time__gt=F('start_time')), name='chk_m8_availability_clock'),
            models.CheckConstraint(condition=Q(day_of_week__gte=1, day_of_week__lte=7), name='chk_m8_availability_day'),
        ]


class WorkloadOverride(Immutable):
    employee = parent('people_master.Employee')
    effective_from = models.DateField()
    effective_to = models.DateField()
    weekly_limit = models.DecimalField(max_digits=6, decimal_places=2)
    actor = parent(settings.AUTH_USER_MODEL)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_m8_workload_override'
        constraints = [
            models.CheckConstraint(condition=Q(effective_to__gte=F('effective_from')), name='chk_m8_override_dates'),
            models.CheckConstraint(condition=Q(weekly_limit__gt=0), name='chk_m8_override_limit'),
        ]


class TimetableAudit(Immutable):
    actor = parent(settings.AUTH_USER_MODEL)
    institution = parent('organization.Institution')
    action = models.CharField(max_length=60)
    resource = models.CharField(max_length=60)
    record_id = models.PositiveBigIntegerField()
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    authority = models.JSONField(default=dict)
    reason = models.CharField(max_length=500)
    correlation_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_m8_audit'


class OutboxEvent(Immutable):
    import uuid
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    institution = parent('organization.Institution')
    topic = models.CharField(max_length=60)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_m8_outbox'


class EventReceipt(Immutable):
    event = parent(OutboxEvent)
    consumer = models.CharField(max_length=80)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_m8_event_receipt'
        constraints = [models.UniqueConstraint(fields=['event', 'consumer'], name='uq_m8_event_consumer')]


class CommandReceipt(Immutable):
    actor = parent(settings.AUTH_USER_MODEL)
    key = models.CharField(max_length=100)
    digest = models.CharField(max_length=64)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_m8_command_receipt'
        constraints = [models.UniqueConstraint(fields=['actor', 'key'], name='uq_m8_command_receipt')]


class SolverJob(Record):
    revision = parent(TimetableRevision)
    status = models.CharField(max_length=10, default='QUEUED', choices=[(v, v) for v in ['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'ACCEPTED']])
    seed = models.PositiveIntegerField(default=0)
    input_snapshot = models.JSONField()
    input_digest = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_m8_solver_job'
        constraints = [models.CheckConstraint(condition=Q(status__in=['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'ACCEPTED']), name='chk_m8_solver_status')]
        indexes = [models.Index(fields=['status', 'created_at'], name='ix_m8_solver_queue')]
