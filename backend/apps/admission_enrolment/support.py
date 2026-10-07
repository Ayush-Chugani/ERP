"""Platform-support records, outside the four academic domain tables."""
import uuid
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import AppendOnlyQuerySet


class Immutable(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('History is append-only.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('History is append-only.')


class AdmissionAudit(Immutable):
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    institution = models.ForeignKey('organization.Institution', on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    resource = models.CharField(max_length=40)
    record_id = models.PositiveBigIntegerField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    request_id = models.UUIDField(default=uuid.uuid4)
    reason = models.CharField(max_length=500)
    changes = models.JSONField(default=dict)

    class Meta:
        db_table = 'platform_admission_audit'
        default_permissions = ('view',)
        indexes = [models.Index(fields=['institution','resource','record_id'], name='m6_audit_record')]


class FeeClearance(Immutable):
    application = models.ForeignKey('admission_enrolment.AdmissionApplication', on_delete=models.PROTECT)
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    reference = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(auto_now_add=True)
    application_version = models.PositiveBigIntegerField()

    class Meta:
        db_table = 'platform_admission_fee_clearance'
        default_permissions = ('view',)
        permissions = [('record_fee_clearance', 'Attest manual admission fee clearance')]


class CommandReceipt(Immutable):
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    application = models.ForeignKey('admission_enrolment.AdmissionApplication', on_delete=models.PROTECT)
    key = models.CharField(max_length=100, db_collation='utf8mb4_bin')
    digest = models.CharField(max_length=64)
    enrolment = models.ForeignKey('admission_enrolment.StudentProgrammeEnrolment', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_admission_receipt'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['actor','application','key'], name='uq_m6_command_receipt')]


class AdmissionOutbox(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.OneToOneField(AdmissionAudit, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=80)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'platform_admission_outbox'
        default_permissions = ()
