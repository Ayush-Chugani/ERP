import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class ImpersonationSession(models.Model):
    session_id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    target=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    started_at=models.DateTimeField(default=timezone.now)
    expires_at=models.DateTimeField()
    ended_at=models.DateTimeField(null=True)
    reason=models.CharField(max_length=500)
    class Meta:
        db_table='platform_iam_impersonation'
        default_permissions=()
        constraints=[models.CheckConstraint(condition=~models.Q(actor=models.F('target')),name='chk_m15_impersonation_distinct'),models.CheckConstraint(condition=models.Q(expires_at__gt=models.F('started_at')),name='chk_m15_impersonation_dates')]
