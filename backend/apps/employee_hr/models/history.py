from django.db import models
from django.db.models import Q, F, Case, When
from apps.people_master.fields import UnsignedBigAutoField, YearField
from apps.student_support.fields import NativeEnumField, CurrentTimestamp
from apps.documents_exit.fields import NativeTimestampField
from ..fields import FixedCharField

class EmployeeQualification(models.Model):
    qualification_level = models.ForeignKey('employee_hr.QualificationLevel', on_delete=models.PROTECT, related_name='+', db_column='qualification_level_id')
    study_mode = models.ForeignKey('employee_hr.StudyMode', on_delete=models.PROTECT, related_name='+', db_column='study_mode_id', null=True, blank=True)
    employee_qualification_id = UnsignedBigAutoField(primary_key=True)
    employee = models.ForeignKey('people_master.Employee', on_delete=models.PROTECT, related_name="+", db_column='employee_id')
    education_institution = models.ForeignKey('employee_hr.EducationInstitution', on_delete=models.PROTECT, related_name="+", db_column='education_institution_id', null=True, blank=True)
    awarding_body = models.ForeignKey('employee_hr.AwardingBody', on_delete=models.PROTECT, related_name="+", db_column='awarding_body_id', null=True, blank=True)
    degree_certificate_name = models.CharField(max_length=250, db_collation='utf8mb4_unicode_ci')
    specialization = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    course_program_name = models.CharField(null=True, blank=True, max_length=250, db_collation='utf8mb4_unicode_ci')
    start_date = models.DateField(null=True, blank=True)
    start_year = YearField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    completion_year = YearField(null=True, blank=True)
    passing_year = YearField(null=True, blank=True)
    registration_roll_number = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    result = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    class_grade = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    cgpa = models.DecimalField(null=True, blank=True, max_digits=6, decimal_places=3)
    cgpa_scale = models.DecimalField(null=True, blank=True, max_digits=6, decimal_places=3)
    percentage = models.DecimalField(null=True, blank=True, max_digits=5, decimal_places=2)
    maximum_marks = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=2)
    marks_obtained = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=2)
    qualification_status = NativeEnumField(choices=[('COMPLETED', 'COMPLETED'), ('PURSUING', 'PURSUING'), ('AWAITING_RESULT', 'AWAITING_RESULT'), ('DISCONTINUED', 'DISCONTINUED'), ('OTHER', 'OTHER')], max_length=15, db_collation='utf8mb4_unicode_ci', default='COMPLETED', db_default='COMPLETED')
    is_highest_qualification = models.BooleanField(default=False, db_default=False)
    active_highest_employee_id = models.GeneratedField(expression=Case(When(is_highest_qualification=True, deleted_at__isnull=True, then=F('employee')), default=None), output_field=models.PositiveBigIntegerField(), db_persist=True, null=True)
    remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    created_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='created_by_user_id', null=True, blank=True)
    updated_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='updated_by_user_id', null=True, blank=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    deleted_at = NativeTimestampField(null=True, blank=True)
    class Meta:
        db_table = 'employee_qualification'
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['employee_qualification_id', 'employee'], name='uq_employee_qualification_owner'),
            models.UniqueConstraint(fields=['active_highest_employee_id'], name='uq_employee_highest_qualification'),
            models.CheckConstraint(condition=Q(completion_date__isnull=True) | Q(start_date__isnull=True) | Q(completion_date__gte=F('start_date')), name='chk_employee_qualification_dates'),
            models.CheckConstraint(condition=Q(percentage__isnull=True) | Q(percentage__gte=0, percentage__lte=100), name='chk_employee_qualification_percentage'),
            models.CheckConstraint(condition=Q(cgpa__isnull=True) | Q(cgpa__gte=0), name='chk_employee_qualification_cgpa'),
            models.CheckConstraint(condition=Q(cgpa_scale__isnull=True) | Q(cgpa_scale__gt=0), name='chk_employee_qualification_cgpa_scale'),
            models.CheckConstraint(condition=Q(cgpa__isnull=True) | Q(cgpa_scale__isnull=True) | Q(cgpa__lte=F('cgpa_scale')), name='chk_employee_qualification_cgpa_range'),
            models.CheckConstraint(condition=Q(marks_obtained__isnull=True) | Q(maximum_marks__isnull=True) | Q(marks_obtained__gte=0, maximum_marks__gte=0, marks_obtained__lte=F('maximum_marks')), name='chk_employee_qualification_marks')
        ]

class EmployeePreviousEmployment(models.Model):
    employee_previous_employment_id = UnsignedBigAutoField(primary_key=True)
    employee = models.ForeignKey('people_master.Employee', on_delete=models.PROTECT, related_name="+", db_column='employee_id')
    previous_organization = models.ForeignKey('employee_hr.PreviousOrganization', on_delete=models.PROTECT, related_name="+", db_column='previous_organization_id')
    department_division = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    designation = models.CharField(max_length=150, db_collation='utf8mb4_unicode_ci')
    employment_type = NativeEnumField(choices=[('FULL_TIME', 'FULL_TIME'), ('PART_TIME', 'PART_TIME'), ('CONTRACT', 'CONTRACT'), ('TEMPORARY', 'TEMPORARY'), ('VISITING', 'VISITING'), ('CONSULTANT', 'CONSULTANT'), ('TRAINEE', 'TRAINEE'), ('SELF_EMPLOYED', 'SELF_EMPLOYED'), ('OTHER', 'OTHER')], max_length=13, db_collation='utf8mb4_unicode_ci')
    nature_of_work = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    employment_start_date = models.DateField()
    employment_end_date = models.DateField(null=True, blank=True)
    experience_days = models.PositiveIntegerField(null=True, blank=True)
    last_drawn_salary = models.DecimalField(null=True, blank=True, max_digits=14, decimal_places=2)
    salary_currency_code = FixedCharField(max_length=3, db_collation='utf8mb4_unicode_ci', default='INR', db_default='INR')
    reason_for_leaving = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    reporting_authority_name = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    reporting_authority_designation = models.CharField(null=True, blank=True, max_length=150, db_collation='utf8mb4_unicode_ci')
    reporting_authority_phone = models.CharField(null=True, blank=True, max_length=25, db_collation='utf8mb4_unicode_ci')
    reporting_authority_email = models.CharField(null=True, blank=True, max_length=254, db_collation='utf8mb4_unicode_ci')
    remarks = models.CharField(null=True, blank=True, max_length=1000, db_collation='utf8mb4_unicode_ci')
    created_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='created_by_user_id', null=True, blank=True)
    updated_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", db_column='updated_by_user_id', null=True, blank=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    deleted_at = NativeTimestampField(null=True, blank=True)
    class Meta:
        db_table = 'employee_previous_employment'
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['employee_previous_employment_id', 'employee'], name='uq_employee_previous_employment_owner'),
            models.CheckConstraint(condition=Q(employment_end_date__isnull=True) | Q(employment_end_date__gte=F('employment_start_date')), name='chk_previous_employment_dates'),
            models.CheckConstraint(condition=Q(last_drawn_salary__isnull=True) | Q(last_drawn_salary__gte=0), name='chk_previous_employment_salary')
        ]
