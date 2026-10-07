from django.db import models
from apps.core.fields import UnsignedAutoField
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import NativeEnumField, CurrentTimestamp
from apps.documents_exit.fields import NativeTimestampField

class QualificationLevel(models.Model):
    qualification_level_id = UnsignedAutoField(primary_key=True, bits=16)
    level_code = models.CharField(unique=True, max_length=40, db_collation='utf8mb4_unicode_ci')
    level_name = models.CharField(unique=True, max_length=120, db_collation='utf8mb4_unicode_ci')
    display_order = models.PositiveSmallIntegerField(default=0, db_default=0)
    is_terminal_degree = models.BooleanField(default=False, db_default=False)
    description = models.CharField(null=True, blank=True, max_length=500, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    class Meta:
        db_table = 'qualification_level'
        default_permissions = ()
        constraints = []

class StudyMode(models.Model):
    study_mode_id = UnsignedAutoField(primary_key=True, bits=8)
    mode_code = models.CharField(unique=True, max_length=30, db_collation='utf8mb4_unicode_ci')
    mode_name = models.CharField(unique=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    class Meta:
        db_table = 'study_mode'
        default_permissions = ()
        constraints = []

class EducationInstitutionType(models.Model):
    education_institution_type_id = UnsignedAutoField(primary_key=True, bits=8)
    type_code = models.CharField(unique=True, max_length=30, db_collation='utf8mb4_unicode_ci')
    type_name = models.CharField(unique=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    class Meta:
        db_table = 'education_institution_type'
        default_permissions = ()
        constraints = []

class AwardingBodyType(models.Model):
    awarding_body_type_id = UnsignedAutoField(primary_key=True, bits=8)
    type_code = models.CharField(unique=True, max_length=30, db_collation='utf8mb4_unicode_ci')
    type_name = models.CharField(unique=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    class Meta:
        db_table = 'awarding_body_type'
        default_permissions = ()
        constraints = []

class EducationInstitution(models.Model):
    education_institution_id = UnsignedBigAutoField(primary_key=True)
    education_institution_type = models.ForeignKey('employee_hr.EducationInstitutionType', on_delete=models.PROTECT, related_name="+", db_column='education_institution_type_id', null=True, blank=True)
    institution_name = models.CharField(max_length=250, db_collation='utf8mb4_unicode_ci')
    city = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    state = models.ForeignKey('common_reference.State', on_delete=models.PROTECT, related_name="+", db_column='state_id', null=True, blank=True)
    country = models.ForeignKey('common_reference.Country', on_delete=models.PROTECT, related_name="+", db_column='country_id', null=True, blank=True)
    website_url = models.CharField(null=True, blank=True, max_length=255, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    class Meta:
        db_table = 'education_institution'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['institution_name', 'city', 'country'], name='uq_education_institution')]

class AwardingBody(models.Model):
    awarding_body_id = UnsignedBigAutoField(primary_key=True)
    awarding_body_type = models.ForeignKey('employee_hr.AwardingBodyType', on_delete=models.PROTECT, related_name="+", db_column='awarding_body_type_id', null=True, blank=True)
    awarding_body_name = models.CharField(max_length=250, db_collation='utf8mb4_unicode_ci')
    university_type = NativeEnumField(null=True, blank=True, choices=[('CENTRAL', 'CENTRAL'), ('STATE', 'STATE'), ('PRIVATE', 'PRIVATE'), ('DEEMED', 'DEEMED'), ('FOREIGN', 'FOREIGN'), ('AUTONOMOUS', 'AUTONOMOUS'), ('OTHER', 'OTHER')], max_length=10, db_collation='utf8mb4_unicode_ci')
    city = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    state = models.ForeignKey('common_reference.State', on_delete=models.PROTECT, related_name="+", db_column='state_id', null=True, blank=True)
    country = models.ForeignKey('common_reference.Country', on_delete=models.PROTECT, related_name="+", db_column='country_id', null=True, blank=True)
    website_url = models.CharField(null=True, blank=True, max_length=255, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    class Meta:
        db_table = 'awarding_body'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['awarding_body_name', 'country'], name='uq_awarding_body')]

class PreviousOrganizationType(models.Model):
    previous_organization_type_id = UnsignedAutoField(primary_key=True, bits=8)
    type_code = models.CharField(unique=True, max_length=40, db_collation='utf8mb4_unicode_ci')
    type_name = models.CharField(unique=True, max_length=120, db_collation='utf8mb4_unicode_ci')
    classification = NativeEnumField(choices=[('INDUSTRY', 'INDUSTRY'), ('ACADEMIC', 'ACADEMIC'), ('GOVERNMENT', 'GOVERNMENT'), ('PRIVATE', 'PRIVATE'), ('PUBLIC_SECTOR', 'PUBLIC_SECTOR'), ('NGO', 'NGO'), ('SELF_EMPLOYED', 'SELF_EMPLOYED'), ('OTHER', 'OTHER')], max_length=13, db_collation='utf8mb4_unicode_ci', default='OTHER', db_default='OTHER')
    is_active = models.BooleanField(default=True, db_default=True)
    class Meta:
        db_table = 'previous_organization_type'
        default_permissions = ()
        constraints = []

class PreviousOrganization(models.Model):
    previous_organization_id = UnsignedBigAutoField(primary_key=True)
    previous_organization_type = models.ForeignKey('employee_hr.PreviousOrganizationType', on_delete=models.PROTECT, related_name="+", db_column='previous_organization_type_id', null=True, blank=True)
    organization_name = models.CharField(max_length=250, db_collation='utf8mb4_unicode_ci')
    address_line_1 = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    address_line_2 = models.CharField(null=True, blank=True, max_length=200, db_collation='utf8mb4_unicode_ci')
    city = models.CharField(null=True, blank=True, max_length=100, db_collation='utf8mb4_unicode_ci')
    state = models.ForeignKey('common_reference.State', on_delete=models.PROTECT, related_name="+", db_column='state_id', null=True, blank=True)
    country = models.ForeignKey('common_reference.Country', on_delete=models.PROTECT, related_name="+", db_column='country_id', null=True, blank=True)
    postal_code = models.CharField(null=True, blank=True, max_length=12, db_collation='utf8mb4_unicode_ci')
    phone = models.CharField(null=True, blank=True, max_length=25, db_collation='utf8mb4_unicode_ci')
    email = models.CharField(null=True, blank=True, max_length=254, db_collation='utf8mb4_unicode_ci')
    website_url = models.CharField(null=True, blank=True, max_length=255, db_collation='utf8mb4_unicode_ci')
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    class Meta:
        db_table = 'previous_organization'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['organization_name', 'city', 'country'], name='uq_previous_organization')]
