from django.conf import settings
from django.db import models
from django.db.models import Q, F, Case, When, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from apps.core.fields import UnsignedAutoField
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import NativeEnumField, CanonicalDateTimeField
from apps.documents_exit.fields import NativeTimestampField
from .model_support import Evidence, LinkProjection, scope_shape

class StudentUserAccount(LinkProjection):
    student = models.OneToOneField('people_master.Student', on_delete=models.PROTECT, related_name="+", db_column='student_id', primary_key=True)
    user = models.OneToOneField('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id', unique=True)
    linked_at = NativeTimestampField(default=timezone.now)
    class Meta:
        db_table = 'student_user_account'
        default_permissions = ()
        managed = False
        constraints = []

class EmployeeUserAccount(LinkProjection):
    employee = models.OneToOneField('people_master.Employee', on_delete=models.PROTECT, related_name="+", db_column='employee_id', primary_key=True)
    user = models.OneToOneField('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id', unique=True)
    linked_at = NativeTimestampField(default=timezone.now)
    class Meta:
        db_table = 'employee_user_account'
        default_permissions = ()
        managed = False
        constraints = []

class AccessModule(models.Model):
    access_module_id = UnsignedAutoField(primary_key=True, bits=16)
    module_code = models.CharField(unique=True, max_length=50, db_collation='utf8mb4_unicode_ci')
    module_name = models.CharField(unique=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    description = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = 'access_module'
        default_permissions = ()
        constraints = []

class AccessResource(models.Model):
    access_resource_id = UnsignedAutoField(primary_key=True, bits=32)
    access_module = models.ForeignKey('identity_access.AccessModule', on_delete=models.PROTECT, related_name="+", db_column='access_module_id')
    resource_code = models.CharField(max_length=80, db_collation='utf8mb4_unicode_ci')
    resource_name = models.CharField(max_length=150, db_collation='utf8mb4_unicode_ci')
    description = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = 'access_resource'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['access_module', 'resource_code'], name='uq_access_resource')]

class AccessAction(models.Model):
    access_action_id = UnsignedAutoField(primary_key=True, bits=8)
    action_code = models.CharField(unique=True, max_length=30, db_collation='utf8mb4_unicode_ci')
    action_name = models.CharField(unique=True, max_length=80, db_collation='utf8mb4_unicode_ci')
    description = models.CharField(null=True, blank=True, max_length=300, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = 'access_action'
        default_permissions = ()
        constraints = []

class Permission(models.Model):
    permission_id = UnsignedAutoField(primary_key=True, bits=32)
    access_resource = models.ForeignKey('identity_access.AccessResource', on_delete=models.PROTECT, related_name="+", db_column='access_resource_id')
    access_action = models.ForeignKey('identity_access.AccessAction', on_delete=models.PROTECT, related_name="+", db_column='access_action_id')
    permission_code = models.CharField(unique=True, max_length=150, db_collation='utf8mb4_unicode_ci')
    permission_name = models.CharField(max_length=200, db_collation='utf8mb4_unicode_ci')
    description = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    is_sensitive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = 'permission'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['access_resource', 'access_action'], name='uq_permission_resource_action')]

class Role(models.Model):
    role_id = UnsignedAutoField(primary_key=True, bits=16)
    parent_role = models.ForeignKey('identity_access.Role', on_delete=models.PROTECT, related_name="+", db_column='parent_role_id', null=True, blank=True)
    role_code = models.CharField(unique=True, max_length=60, db_collation='utf8mb4_unicode_ci')
    role_name = models.CharField(unique=True, max_length=120, db_collation='utf8mb4_unicode_ci')
    role_category = NativeEnumField(choices=[('SYSTEM', 'SYSTEM'), ('GOVERNANCE', 'GOVERNANCE'), ('ACADEMIC', 'ACADEMIC'), ('ADMINISTRATIVE', 'ADMINISTRATIVE'), ('FACULTY', 'FACULTY'), ('STUDENT', 'STUDENT'), ('PARENT', 'PARENT'), ('AUDIT', 'AUDIT'), ('SUPPORT', 'SUPPORT')], max_length=14, db_collation='utf8mb4_unicode_ci')
    role_level = NativeEnumField(choices=[('GLOBAL', 'GLOBAL'), ('INSTITUTION', 'INSTITUTION'), ('CAMPUS', 'CAMPUS'), ('DEPARTMENT', 'DEPARTMENT'), ('PROGRAMME', 'PROGRAMME'), ('SELF', 'SELF')], max_length=11, db_collation='utf8mb4_unicode_ci', default='GLOBAL')
    description = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    is_system_role = models.BooleanField(default=False)
    is_assignable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = NativeTimestampField(default=timezone.now)
    updated_at = NativeTimestampField(auto_now=True)
    class Meta:
        db_table = 'role'
        default_permissions = ()
        constraints = []

class RolePermission(models.Model):
    role = models.ForeignKey('identity_access.Role', on_delete=models.PROTECT, related_name="+", db_column='role_id')
    permission = models.ForeignKey('identity_access.Permission', on_delete=models.PROTECT, related_name="+", db_column='permission_id')
    permission_effect = NativeEnumField(choices=[('ALLOW', 'ALLOW'), ('DENY', 'DENY')], max_length=5, db_collation='utf8mb4_unicode_ci', default='ALLOW')
    granted_at = CanonicalDateTimeField(default=timezone.now)
    pk = models.CompositePrimaryKey('role', 'permission')
    class Meta:
        db_table = 'role_permission'
        default_permissions = ()
        constraints = []

class UserRoleAssignment(models.Model):
    user_role_assignment_id = UnsignedBigAutoField(primary_key=True)
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id')
    role = models.ForeignKey('identity_access.Role', on_delete=models.PROTECT, related_name="+", db_column='role_id')
    scope_type = NativeEnumField(choices=[('GLOBAL', 'GLOBAL'), ('INSTITUTION', 'INSTITUTION'), ('CAMPUS', 'CAMPUS'), ('DEPARTMENT', 'DEPARTMENT'), ('PROGRAMME', 'PROGRAMME'), ('SELF', 'SELF')], max_length=11, db_collation='utf8mb4_unicode_ci', default='GLOBAL')
    institution = models.ForeignKey('organization.Institution', on_delete=models.PROTECT, related_name="+", db_column='institution_id', null=True, blank=True)
    campus = models.ForeignKey('organization.Campus', on_delete=models.PROTECT, related_name="+", db_column='campus_id', null=True, blank=True)
    department = models.ForeignKey('organization.Department', on_delete=models.PROTECT, related_name="+", db_column='department_id', null=True, blank=True)
    programme = models.ForeignKey('organization.Programme', on_delete=models.PROTECT, related_name="+", db_column='programme_id', null=True, blank=True)
    scope_entity_id = models.GeneratedField(expression=Case(When(scope_type='GLOBAL', then=Value(0)), When(scope_type='SELF', then=F('user')), When(scope_type='INSTITUTION', then=F('institution')), When(scope_type='CAMPUS', then=F('campus')), When(scope_type='DEPARTMENT', then=F('department')), When(scope_type='PROGRAMME', then=F('programme')), output_field=models.BigIntegerField()), output_field=models.PositiveBigIntegerField(), db_persist=True)
    valid_from = CanonicalDateTimeField(default=timezone.now)
    valid_to = CanonicalDateTimeField(null=True, blank=True)
    assignment_status = NativeEnumField(choices=[('PENDING', 'PENDING'), ('ACTIVE', 'ACTIVE'), ('SUSPENDED', 'SUSPENDED'), ('EXPIRED', 'EXPIRED'), ('REVOKED', 'REVOKED')], max_length=9, db_collation='utf8mb4_unicode_ci', default='ACTIVE')
    is_primary = models.BooleanField(default=False)
    assigned_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='assigned_by_user_id', null=True, blank=True)
    assignment_reason = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    created_at = NativeTimestampField(default=timezone.now)
    class Meta:
        db_table = 'user_role_assignment'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['user', 'role', 'scope_type', 'scope_entity_id', 'valid_from'], name='uq_user_role_assignment'), models.CheckConstraint(condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')), name='chk_user_role_dates'), models.CheckConstraint(condition=scope_shape(), name='chk_user_role_scope')]

class UserPermissionOverride(models.Model):
    user_permission_override_id = UnsignedBigAutoField(primary_key=True)
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id')
    permission = models.ForeignKey('identity_access.Permission', on_delete=models.PROTECT, related_name="+", db_column='permission_id')
    permission_effect = NativeEnumField(choices=[('ALLOW', 'ALLOW'), ('DENY', 'DENY')], max_length=5, db_collation='utf8mb4_unicode_ci')
    scope_type = NativeEnumField(choices=[('GLOBAL', 'GLOBAL'), ('INSTITUTION', 'INSTITUTION'), ('CAMPUS', 'CAMPUS'), ('DEPARTMENT', 'DEPARTMENT'), ('PROGRAMME', 'PROGRAMME'), ('SELF', 'SELF')], max_length=11, db_collation='utf8mb4_unicode_ci', default='GLOBAL')
    scope_entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    normalized_scope_entity_id = models.GeneratedField(expression=Case(When(scope_type__in=['GLOBAL','SELF'], then=Value(0)), default=Coalesce('scope_entity_id', Value(0)), output_field=models.BigIntegerField()), output_field=models.PositiveBigIntegerField(), db_persist=True)
    valid_from = CanonicalDateTimeField(default=timezone.now)
    valid_to = CanonicalDateTimeField(null=True, blank=True)
    granted_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='granted_by_user_id', null=True, blank=True)
    justification = models.CharField(max_length=500, db_collation='utf8mb4_unicode_ci')
    created_at = NativeTimestampField(default=timezone.now)
    revoked_at = CanonicalDateTimeField(null=True, blank=True)
    class Meta:
        db_table = 'user_permission_override'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['user', 'permission', 'scope_type', 'normalized_scope_entity_id', 'valid_from'], name='uq_user_permission_override'), models.CheckConstraint(condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')), name='chk_user_permission_override_dates'), models.CheckConstraint(condition=(Q(scope_type__in=['GLOBAL','SELF'], scope_entity_id__isnull=True) | Q(scope_type__in=['INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME'], scope_entity_id__isnull=False)), name='chk_user_permission_override_scope')]

class RoleDelegation(models.Model):
    role_delegation_id = UnsignedBigAutoField(primary_key=True)
    delegator_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='delegator_user_id')
    delegate_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='delegate_user_id')
    source_assignment = models.ForeignKey('identity_access.UserRoleAssignment', on_delete=models.PROTECT, related_name="+", db_column='source_assignment_id')
    valid_from = CanonicalDateTimeField()
    valid_to = CanonicalDateTimeField()
    delegation_status = NativeEnumField(choices=[('PENDING', 'PENDING'), ('ACTIVE', 'ACTIVE'), ('REVOKED', 'REVOKED'), ('EXPIRED', 'EXPIRED')], max_length=7, db_collation='utf8mb4_unicode_ci', default='PENDING')
    reason = models.CharField(max_length=500, db_collation='utf8mb4_unicode_ci')
    approved_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='approved_by_user_id', null=True, blank=True)
    created_at = NativeTimestampField(default=timezone.now)
    class Meta:
        db_table = 'role_delegation'
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=Q(valid_to__gt=F('valid_from')), name='chk_role_delegation_dates'), models.CheckConstraint(condition=~Q(delegator_user=F('delegate_user')), name='chk_role_delegation_users')]

class PasswordHistory(Evidence):
    password_history_id = UnsignedBigAutoField(primary_key=True)
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id')
    password_hash = models.CharField(max_length=255, db_collation='utf8mb4_unicode_ci')
    changed_at = CanonicalDateTimeField(default=timezone.now)
    class Meta:
        db_table = 'password_history'
        default_permissions = ()
        constraints = []

class LoginAudit(Evidence):
    login_audit_id = UnsignedBigAutoField(primary_key=True)
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id', null=True, blank=True)
    username_attempted = models.CharField(max_length=100, db_collation='utf8mb4_unicode_ci')
    login_at = CanonicalDateTimeField(default=timezone.now)
    logout_at = CanonicalDateTimeField(null=True, blank=True)
    ip_address = models.CharField(null=True, blank=True, max_length=45, db_collation='utf8mb4_unicode_ci')
    user_agent = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    was_successful = models.BooleanField()
    failure_reason = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    session_identifier = models.CharField(null=True, blank=True, max_length=128, db_collation='utf8mb4_unicode_ci')
    class Meta:
        db_table = 'login_audit'
        default_permissions = ()
        constraints = []

class ActivityAudit(Evidence):
    activity_audit_id = UnsignedBigAutoField(primary_key=True)
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='user_id', null=True, blank=True)
    module_code = models.CharField(max_length=50, db_collation='utf8mb4_unicode_ci')
    action_code = models.CharField(max_length=30, db_collation='utf8mb4_unicode_ci')
    entity_name = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    entity_id = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    activity_at = CanonicalDateTimeField(default=timezone.now)
    ip_address = models.CharField(null=True, blank=True, max_length=45, db_collation='utf8mb4_unicode_ci')
    request_identifier = models.CharField(null=True, blank=True, max_length=128, db_collation='utf8mb4_unicode_ci')
    before_values = models.JSONField(null=True, blank=True)
    after_values = models.JSONField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    class Meta:
        db_table = 'activity_audit'
        default_permissions = ()
        constraints = []

from .support_models import ImpersonationSession
