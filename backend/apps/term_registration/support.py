from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import AppendOnlyQuerySet


class AppendOnly(models.Model):
    objects=AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract=True

    def save(self,*args,**kwargs):
        if not self._state.adding:
            raise ValidationError('Registration evidence is append-only.')
        kwargs['force_insert']=True
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Registration evidence is append-only.')


class ProgressionApproval(AppendOnly):
    enrolment=models.ForeignKey('admission_enrolment.StudentProgrammeEnrolment',on_delete=models.PROTECT)
    offering=models.ForeignKey('term_registration.ProgrammeTermOffering',on_delete=models.PROTECT)
    enrolment_version=models.PositiveBigIntegerField()
    offering_version=models.PositiveBigIntegerField()
    actor=models.ForeignKey('accounts.User',on_delete=models.PROTECT)
    reason=models.CharField(max_length=500)
    approved_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table='platform_registration_progression'
        default_permissions=('view',)
        indexes=[models.Index(fields=['enrolment','offering','enrolment_version','offering_version'],name='m7_progression_lookup')]


class RegistrationAudit(AppendOnly):
    actor=models.ForeignKey('accounts.User',on_delete=models.PROTECT)
    programme=models.ForeignKey('organization.Programme',on_delete=models.PROTECT)
    resource=models.CharField(max_length=60)
    record_id=models.PositiveBigIntegerField()
    action=models.CharField(max_length=30)
    reason=models.CharField(max_length=500)
    occurred_at=models.DateTimeField(auto_now_add=True)
    before=models.JSONField(default=dict,blank=True)
    after=models.JSONField(default=dict,blank=True)

    class Meta:
        db_table='platform_registration_audit'
        default_permissions=('view',)


class RegistrationPolicy(models.Model):
    programme = models.OneToOneField('organization.Programme', on_delete=models.PROTECT)
    maximum_credits = models.DecimalField(max_digits=6, decimal_places=1)
    minimum_credits = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    version = models.PositiveBigIntegerField(default=1)
    updated_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_registration_policy'
        constraints = [models.CheckConstraint(condition=models.Q(maximum_credits__gt=0, minimum_credits__gte=0, minimum_credits__lte=models.F('maximum_credits')), name='chk_m7_credit_policy')]
        permissions = [('configure_registration', 'Configure registration credit policy'), ('authorize_special_course', 'Authorize noncurriculum course offerings')]


class CommandReceipt(AppendOnly):
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+')
    key = models.CharField(max_length=100)
    digest = models.CharField(max_length=64)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_registration_receipt'
        constraints = [models.UniqueConstraint(fields=['actor', 'key'], name='uq_m7_command_receipt')]


class RegistrationEvent(AppendOnly):
    audit = models.OneToOneField(RegistrationAudit, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=60)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_registration_event'


class EventDelivery(AppendOnly):
    event = models.ForeignKey(RegistrationEvent, on_delete=models.PROTECT)
    consumer = models.CharField(max_length=80)
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_registration_delivery'
        constraints = [models.UniqueConstraint(fields=['event', 'consumer'], name='uq_m7_delivery')]
