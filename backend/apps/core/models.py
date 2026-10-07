"""Platform-support audit storage; deliberately separate from domain tables."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Audit events cannot be updated.')

    def delete(self):
        raise ValidationError('Audit events cannot be deleted.')

    def bulk_create(self, *args, **kwargs):
        raise ValidationError('Create audit events individually through the write service.')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be updated.')


class ReferenceAuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=12, choices=[(x, x) for x in ('create', 'update', 'deactivate', 'reactivate')])
    resource = models.CharField(max_length=40)
    record_id = models.PositiveBigIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=8, choices=[(x, x) for x in ('api', 'admin', 'seed')])
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = 'platform_reference_audit'
        ordering = ['-timestamp', '-pk']
        default_permissions = ('view',)
        indexes = [models.Index(fields=['resource', 'record_id'], name='audit_reference_record')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Audit events cannot be updated.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be deleted.')
