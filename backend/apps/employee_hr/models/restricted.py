from django.db import models
from django.db.models import Q, F, Case, When
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import NativeEnumField, CurrentTimestamp
from apps.documents_exit.fields import NativeTimestampField
from ..fields import FixedCharField, VarBinaryField


class EmployeeBankAccount(models.Model):
    employee_bank_account_id = UnsignedBigAutoField(primary_key=True)
    employee = models.ForeignKey('people_master.Employee', on_delete=models.PROTECT, related_name='+', db_column='employee_id')
    account_holder_name = models.CharField(max_length=200, db_collation='utf8mb4_unicode_ci')
    bank_name = models.CharField(max_length=200, db_collation='utf8mb4_unicode_ci')
    branch_name = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    account_number_ciphertext = VarBinaryField(max_length=1024)
    account_number_fingerprint = FixedCharField(unique=True, max_length=64, db_collation='utf8mb4_unicode_ci')
    account_number_last4 = FixedCharField(max_length=4, db_collation='utf8mb4_unicode_ci')
    account_number_confirmed = models.BooleanField(db_default=False, default=False)
    account_type = NativeEnumField(choices=[('SAVINGS', 'SAVINGS'), ('CURRENT', 'CURRENT'), ('SALARY', 'SALARY'), ('NRE', 'NRE'), ('NRO', 'NRO'), ('OTHER', 'OTHER')], max_length=7, db_collation='utf8mb4_unicode_ci', db_default='SAVINGS', default='SAVINGS')
    ifsc_code = models.CharField(max_length=11, db_collation='utf8mb4_unicode_ci')
    micr_code = models.CharField(null=True, blank=True, max_length=20, db_collation='utf8mb4_unicode_ci')
    branch_code = models.CharField(null=True, blank=True, max_length=30, db_collation='utf8mb4_unicode_ci')
    bank_address = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    city = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    state = models.ForeignKey('common_reference.State', on_delete=models.PROTECT, related_name='+', db_column='state_id', null=True, blank=True)
    country = models.ForeignKey('common_reference.Country', on_delete=models.PROTECT, related_name='+', db_column='country_id', null=True, blank=True)
    upi_id = models.CharField(null=True, blank=True, max_length=150, db_collation='utf8mb4_unicode_ci')
    is_salary_account = models.BooleanField(db_default=False, default=False)
    is_primary = models.BooleanField(db_default=False, default=False)
    account_status = NativeEnumField(choices=[('PENDING_VERIFICATION', 'PENDING_VERIFICATION'), ('ACTIVE', 'ACTIVE'), ('INACTIVE', 'INACTIVE'), ('CLOSED', 'CLOSED'), ('REJECTED', 'REJECTED')], max_length=20, db_collation='utf8mb4_unicode_ci', db_default='PENDING_VERIFICATION', default='PENDING_VERIFICATION')
    verification_status = NativeEnumField(choices=[('PENDING', 'PENDING'), ('VERIFIED', 'VERIFIED'), ('REJECTED', 'REJECTED'), ('EXPIRED', 'EXPIRED')], max_length=8, db_collation='utf8mb4_unicode_ci', db_default='PENDING', default='PENDING')
    verified_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='verified_by_user_id', null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    created_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='created_by_user_id', null=True, blank=True)
    updated_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='updated_by_user_id', null=True, blank=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    deleted_at = NativeTimestampField(null=True, blank=True)
    active_primary_employee_id = models.GeneratedField(expression=Case(When(is_primary=True, deleted_at__isnull=True, then=F('employee')), default=None), output_field=models.PositiveBigIntegerField(), db_persist=True, null=True)
    class Meta:
        db_table = 'employee_bank_account'
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['employee_bank_account_id', 'employee'], name='uq_employee_bank_owner'),
            models.UniqueConstraint(fields=['active_primary_employee_id'], name='uq_employee_primary_bank'),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_from__isnull=True) | Q(effective_to__gte=F('effective_from')), name='chk_employee_bank_dates'),
            models.CheckConstraint(condition=Q(account_number_last4__regex=r'^[0-9]{4}$'), name='chk_employee_bank_last4'),
            models.CheckConstraint(condition=Q(ifsc_code__regex=r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$'), name='chk_employee_bank_ifsc'),
        ]

class EmployeePan(models.Model):
    employee_pan_id = UnsignedBigAutoField(primary_key=True)
    employee = models.OneToOneField('people_master.Employee', on_delete=models.PROTECT, related_name='+', db_column='employee_id')
    pan_number_ciphertext = VarBinaryField(max_length=1024)
    pan_number_fingerprint = FixedCharField(unique=True, max_length=64, db_collation='utf8mb4_unicode_ci')
    pan_number_masked = models.CharField(max_length=15, db_collation='utf8mb4_unicode_ci')
    name_as_per_pan = models.CharField(max_length=200, db_collation='utf8mb4_unicode_ci')
    pan_issue_date = models.DateField(null=True, blank=True)
    pan_issue_details = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    format_validated = models.BooleanField(db_default=False, default=False)
    verification_status = NativeEnumField(choices=[('PENDING', 'PENDING'), ('VERIFIED', 'VERIFIED'), ('REJECTED', 'REJECTED'), ('EXPIRED', 'EXPIRED')], max_length=8, db_collation='utf8mb4_unicode_ci', db_default='PENDING', default='PENDING')
    verified_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='verified_by_user_id', null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    created_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='created_by_user_id', null=True, blank=True)
    updated_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='updated_by_user_id', null=True, blank=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    deleted_at = NativeTimestampField(null=True, blank=True)
    class Meta:
        db_table = 'employee_pan'
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['employee_pan_id', 'employee'], name='uq_employee_pan_owner'),
            models.CheckConstraint(condition=GreaterThanOrEqual(Length('pan_number_masked'), 6) & LessThanOrEqual(Length('pan_number_masked'), 15), name='chk_employee_pan_masked'),
        ]

class EmployeeAadhaar(models.Model):
    employee_aadhaar_id = UnsignedBigAutoField(primary_key=True)
    employee = models.OneToOneField('people_master.Employee', on_delete=models.PROTECT, related_name='+', db_column='employee_id')
    aadhaar_number_ciphertext = VarBinaryField(max_length=1024)
    aadhaar_number_fingerprint = FixedCharField(unique=True, max_length=64, db_collation='utf8mb4_unicode_ci')
    aadhaar_number_last4 = FixedCharField(max_length=4, db_collation='utf8mb4_unicode_ci')
    aadhaar_number_masked = models.CharField(max_length=30, db_collation='utf8mb4_unicode_ci')
    name_as_per_aadhaar = models.CharField(max_length=200, db_collation='utf8mb4_unicode_ci')
    format_validated = models.BooleanField(db_default=False, default=False)
    verification_status = NativeEnumField(choices=[('PENDING', 'PENDING'), ('VERIFIED', 'VERIFIED'), ('REJECTED', 'REJECTED'), ('EXPIRED', 'EXPIRED')], max_length=8, db_collation='utf8mb4_unicode_ci', db_default='PENDING', default='PENDING')
    verified_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='verified_by_user_id', null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    collection_purpose = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    created_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='created_by_user_id', null=True, blank=True)
    updated_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+', db_column='updated_by_user_id', null=True, blank=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    deleted_at = NativeTimestampField(null=True, blank=True)
    class Meta:
        db_table = 'employee_aadhaar'
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['employee_aadhaar_id', 'employee'], name='uq_employee_aadhaar_owner'),
            models.CheckConstraint(condition=Q(aadhaar_number_last4__regex=r'^[0-9]{4}$'), name='chk_employee_aadhaar_last4'),
        ]
