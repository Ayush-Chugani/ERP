from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.student_support.fields import NativeEnumField, CanonicalDateTimeField

class User(AbstractUser):
    user_id = models.BigAutoField(primary_key=True, db_column="user_id")
    # Additive M15 compatibility: retain AbstractUser and existing password/IDs.
    account_status = NativeEnumField(max_length=8, choices=[(v, v) for v in
        ('PENDING', 'ACTIVE', 'LOCKED', 'DISABLED', 'EXPIRED')], default='ACTIVE')
    must_change_password = models.BooleanField(default=False)
    multi_factor_enabled = models.BooleanField(default=False)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    locked_until = CanonicalDateTimeField(null=True, blank=True)
    password_changed_at = CanonicalDateTimeField(null=True, blank=True)
    last_login_at = CanonicalDateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    security_version = models.PositiveBigIntegerField(default=0)
    class Meta:
        db_table = "user_account"
        ordering = ["user_id"]
        permissions = [("manage_platform_access", "Manage global platform permissions")]
