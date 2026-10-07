from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.fields import UnsignedAutoField
from apps.core.models import AppendOnlyQuerySet
from apps.people_master.fields import UnsignedBigAutoField

from . import policies as p
from .fields import (
    CanonicalDateTimeField,
    CanonicalTextField,
    CurrentTimestamp,
    NativeEnumField,
)


def enum(values, default):
    return NativeEnumField(
        max_length=max(map(len, values)),
        choices=[(x, x) for x in values],
        default=default,
        db_default=default,
    )


def fk(model, **kw):
    return models.ForeignKey(model, on_delete=models.PROTECT, db_index=False, **kw)


class MentorAssignment(models.Model):
    mentor_assignment_id = UnsignedBigAutoField(primary_key=True)
    student = fk("people_master.Student")
    employee = fk("people_master.Employee")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    assignment_status = enum(p.ASSIGNMENT, "ACTIVE")

    class Meta:
        db_table = "mentor_assignment"
        default_permissions = ()
        permissions: ClassVar[list] = [
            (cap, cap.replace("_", " ")) for cap in p.CAPABILITIES
        ]

    def __str__(self):
        return f"Mentor assignment {self.pk}"

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must not precede start date.")


class CounsellingSession(models.Model):
    counselling_session_id = UnsignedBigAutoField(primary_key=True)
    mentor_assignment = fk(MentorAssignment)
    session_date = CanonicalDateTimeField()
    observations = CanonicalTextField(null=True, blank=True)
    action_plan = CanonicalTextField(null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    session_status = enum(p.SESSION, "COMPLETED")
    confidentiality_level = enum(p.LEVELS, "RESTRICTED")

    class Meta:
        db_table = "counselling_session"
        default_permissions = ()

    def __str__(self):
        return f"Counselling session {self.pk}"


class GrievanceCategory(models.Model):
    grievance_category_id = UnsignedAutoField(bits=16, primary_key=True)
    category_code = models.CharField(max_length=30, unique=True)
    category_name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "grievance_category"
        default_permissions = ()

    def __str__(self):
        return self.category_name


class Grievance(models.Model):
    grievance_id = UnsignedBigAutoField(primary_key=True)
    grievance_number = models.CharField(max_length=30, unique=True)
    student = fk("people_master.Student")
    grievance_category = fk(GrievanceCategory)
    department = fk("organization.Department", null=True, blank=True)
    submitted_at = CanonicalDateTimeField(db_default=CurrentTimestamp())
    subject = models.CharField(max_length=200)
    description = CanonicalTextField()
    priority = enum(p.PRIORITY, "NORMAL")
    status = enum(p.STATUS, "SUBMITTED")
    resolved_at = CanonicalDateTimeField(null=True, blank=True)
    resolution = CanonicalTextField(null=True, blank=True)

    class Meta:
        db_table = "grievance"
        default_permissions = ()

    def __str__(self):
        return self.grievance_number


class GrievanceAction(models.Model):
    grievance_action_id = UnsignedBigAutoField(primary_key=True)
    grievance = fk(Grievance)
    action_at = CanonicalDateTimeField(db_default=CurrentTimestamp())
    action_type = models.CharField(max_length=50, choices=[(x, x) for x in p.ACTIONS])
    action_notes = CanonicalTextField(null=True, blank=True)
    new_status = models.CharField(
        max_length=30, null=True, blank=True, choices=[(x, x) for x in p.STATUS]
    )
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = "grievance_action"
        default_permissions = ()

    def __str__(self):
        return f"Grievance action {self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("History is append-only.")
        self.full_clean()
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("History is append-only.")
