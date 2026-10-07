from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from apps.core.fields import UnsignedAutoField, ReferenceTextField
from apps.core.models import AppendOnlyQuerySet
from apps.organization.fields import UnsignedTinyIntegerField
from .enums import YearStatus, TermStatus, TermType

COLLATION = 'utf8mb4_unicode_ci'


def text(length, **kwargs):
    return ReferenceTextField(max_length=length, db_collation=COLLATION, **kwargs)


class AcademicYear(models.Model):
    academic_year_id = UnsignedAutoField(bits=16, primary_key=True)
    year_code = text(9, kind='code', unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=7, choices=YearStatus.choices, default='PLANNED', db_default='PLANNED')

    class Meta:
        db_table = 'academic_year'
        ordering = ['-start_date', 'pk']
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gt=F('start_date')), name='chk_academic_year_dates'),
            models.CheckConstraint(condition=Q(status__in=YearStatus.values), name='chk_academic_year_status'),
        ]
        indexes = [models.Index(fields=['status', 'start_date'], name='calendar_year_status')]
        permissions = [('activate_academicyear', 'Activate academic year'), ('close_academicyear', 'Close academic year'), ('reopen_academicyear', 'Reopen academic year')]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({'end_date': 'Must be after start date.'})

    def __str__(self):
        return self.year_code


class AcademicTerm(models.Model):
    academic_term_id = UnsignedAutoField(bits=32, primary_key=True)
    academic_year = models.ForeignKey(AcademicYear, db_column='academic_year_id', on_delete=models.PROTECT, related_name='terms')
    term_code = text(20, kind='code')
    term_name = text(100)
    term_type = models.CharField(max_length=6, choices=TermType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_start_date = models.DateField(null=True, blank=True)
    registration_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=17, choices=TermStatus.choices, default='PLANNED', db_default='PLANNED')

    class Meta:
        db_table = 'academic_term'
        ordering = ['start_date', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['academic_year', 'term_code'], name='uq_term_code'),
            models.CheckConstraint(condition=Q(end_date__gte=F('start_date')), name='chk_term_dates'),
            models.CheckConstraint(condition=Q(registration_start_date__isnull=True) | Q(registration_end_date__isnull=True) | Q(registration_end_date__gte=F('registration_start_date')), name='chk_term_registration_dates'),
            models.CheckConstraint(condition=Q(status__in=TermStatus.values), name='chk_academic_term_status'),
            models.CheckConstraint(condition=Q(term_type__in=TermType.values), name='chk_academic_term_type'),
        ]
        indexes = [models.Index(fields=['status', 'start_date'], name='calendar_term_status')]
        permissions = [('activate_academicterm', 'Activate academic term'), ('close_academicterm', 'Close academic term'), ('reopen_academicterm', 'Reopen academic term'), ('open_registration_academicterm', 'Open term registration')]

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'Must be on or after start date.'
        if self.registration_start_date and self.registration_end_date and self.registration_end_date < self.registration_start_date:
            errors['registration_end_date'] = 'Must be on or after registration start.'
        if self.academic_year_id:
            year = self.academic_year
            for name in ('start_date', 'end_date', 'registration_start_date', 'registration_end_date'):
                value = getattr(self, name)
                if value and not year.start_date <= value <= year.end_date:
                    errors[name] = 'Must be within the academic year.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.term_name


class Semester(models.Model):
    semester_id = UnsignedAutoField(bits=8, primary_key=True)
    semester_number = UnsignedTinyIntegerField(unique=True)
    semester_name = text(50, unique=True)

    class Meta:
        db_table = 'semester'
        ordering = ['semester_number', 'pk']
        constraints = [models.CheckConstraint(condition=Q(semester_number__gt=0), name='chk_semester_number')]

    def __str__(self):
        return self.semester_name


class TimeSlot(models.Model):
    time_slot_id = UnsignedAutoField(bits=16, primary_key=True)
    campus = models.ForeignKey('organization.Campus', db_column='campus_id', on_delete=models.PROTECT, related_name='calendar_time_slots')
    slot_code = text(20, kind='code')
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False, db_default=False)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = 'time_slot'
        ordering = ['start_time', 'end_time', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['campus', 'slot_code'], name='uq_time_slot'),
            models.CheckConstraint(condition=Q(end_time__gt=F('start_time')), name='chk_time_slot'),
        ]
        indexes = [models.Index(fields=['campus', 'is_active', 'start_time'], name='calendar_slot_available')]
        permissions = [('activate_timeslot', 'Activate time slot'), ('deactivate_timeslot', 'Deactivate time slot')]

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'Must be after start time; overnight slots are not supported.'})

    def __str__(self):
        return self.slot_code


class CalendarAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    institution = models.ForeignKey('organization.Institution', null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=24)
    resource = models.CharField(max_length=32)
    record_id = models.PositiveBigIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=64)
    reason = models.CharField(max_length=250, blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = 'platform_calendar_audit'
        default_permissions = ('view',)
        ordering = ['-timestamp', '-pk']
        indexes = [models.Index(fields=['resource', 'record_id'], name='calendar_audit_record')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Audit events cannot be updated.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be deleted.')
