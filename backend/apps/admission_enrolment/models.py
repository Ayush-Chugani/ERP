from django.db import models
from django.db.models import Q, F
from apps.people_master.fields import UnsignedBigAutoField

from .support import Immutable, AdmissionAudit, FeeClearance, CommandReceipt, AdmissionOutbox

class Validated(models.Model):
    class Meta:
        abstract = True
    def clean(self):
        from .validation import clean_record
        clean_record(self)

class AdmissionApplicant(Validated):
    institution = models.ForeignKey('organization.Institution', on_delete=models.PROTECT, related_name="+", )
    canonical_student = models.ForeignKey('people_master.Student', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    updated_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    admission_applicant_id = UnsignedBigAutoField(primary_key=True)
    first_name = models.CharField(max_length=100, db_collation="utf8mb4_unicode_ci")
    middle_name = models.CharField(null=True, blank=True, max_length=100, db_collation="utf8mb4_unicode_ci")
    last_name = models.CharField(null=True, blank=True, max_length=100, db_collation="utf8mb4_unicode_ci")
    display_name = models.CharField(max_length=250, db_collation="utf8mb4_unicode_ci")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.ForeignKey('common_reference.Gender', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    primary_email = models.EmailField(null=True, blank=True, max_length=254, db_collation="utf8mb4_unicode_ci")
    primary_phone = models.CharField(null=True, blank=True, max_length=25, db_collation="utf8mb4_unicode_ci")
    nationality_country = models.ForeignKey('common_reference.Country', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    social_category = models.ForeignKey('common_reference.SocialCategory', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    caste = models.ForeignKey('common_reference.Caste', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    sub_caste = models.ForeignKey('common_reference.SubCaste', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'admission_applicant'
        ordering = ['pk']
        constraints = []
        indexes = [models.Index(fields=['institution', 'primary_email'], name='ix_m6_applicant_email'), models.Index(fields=['institution', 'primary_phone'], name='ix_m6_applicant_phone'), models.Index(fields=['institution', 'display_name'], name='ix_m6_applicant_name')]

class AdmissionApplication(Validated):
    version = models.PositiveBigIntegerField(default=1)
    reviewer = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    updated_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    application_id = UnsignedBigAutoField(primary_key=True)
    application_number = models.CharField(max_length=30, unique=True, db_collation="utf8mb4_unicode_ci")
    admission_applicant = models.ForeignKey('admission_enrolment.AdmissionApplicant', on_delete=models.PROTECT, related_name="+", )
    admitted_student = models.ForeignKey('people_master.Student', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    programme = models.ForeignKey('organization.Programme', on_delete=models.PROTECT, related_name="+", )
    specialization = models.ForeignKey('organization.ProgrammeSpecialization', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    academic_year = models.ForeignKey('academic_calendar.AcademicYear', on_delete=models.PROTECT, related_name="+", )
    admission_category = models.ForeignKey('common_reference.AdmissionCategory', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    application_date = models.DateField()
    class ApplicationStatus(models.TextChoices):
        DRAFT = 'DRAFT'
        SUBMITTED = 'SUBMITTED'
        UNDER_REVIEW = 'UNDER_REVIEW'
        ELIGIBLE = 'ELIGIBLE'
        INELIGIBLE = 'INELIGIBLE'
        SELECTED = 'SELECTED'
        WAITLISTED = 'WAITLISTED'
        REJECTED = 'REJECTED'
        ADMITTED = 'ADMITTED'
        CANCELLED = 'CANCELLED'
    application_status = models.CharField(max_length=12, choices=ApplicationStatus.choices, default='DRAFT', db_collation="utf8mb4_unicode_ci")
    class EligibilityStatus(models.TextChoices):
        PENDING = 'PENDING'
        ELIGIBLE = 'ELIGIBLE'
        INELIGIBLE = 'INELIGIBLE'
    eligibility_status = models.CharField(max_length=10, choices=EligibilityStatus.choices, default='PENDING', db_collation="utf8mb4_unicode_ci")
    remarks = models.TextField(null=True, blank=True, db_collation="utf8mb4_unicode_ci")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'admission_application'
        permissions = [(a + '_admission', a.title() + ' admissions') for a in ('review','select','admit','reopen','export','sensitive','lifecycle')]
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['application_id', 'admitted_student'], name='uq_m6_application_student'), models.CheckConstraint(condition=Q(application_status='ADMITTED', admitted_student__isnull=False) | (~Q(application_status='ADMITTED') & Q(admitted_student__isnull=True)), name='chk_m6_application_conversion'), models.CheckConstraint(condition=~Q(application_status__in=['ELIGIBLE','SELECTED','ADMITTED']) | Q(eligibility_status='ELIGIBLE'), name='chk_m6_application_eligible')]
        indexes = [models.Index(fields=['programme', 'academic_year', 'application_status', 'application_id'], name='ix_m6_application_queue')]

class StudentProgrammeEnrolment(Validated):
    application = models.OneToOneField('admission_enrolment.AdmissionApplication', on_delete=models.PROTECT, related_name="+", unique=True)
    transfer_from = models.OneToOneField('admission_enrolment.StudentProgrammeEnrolment', on_delete=models.PROTECT, related_name="+", null=True, blank=True, unique=True)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    updated_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    enrolment_id = UnsignedBigAutoField(primary_key=True)
    student = models.ForeignKey('people_master.Student', on_delete=models.PROTECT, related_name="+", )
    programme = models.ForeignKey('organization.Programme', on_delete=models.PROTECT, related_name="+", )
    specialization = models.ForeignKey('organization.ProgrammeSpecialization', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    curriculum_scheme = models.ForeignKey('curriculum_catalog.CurriculumScheme', on_delete=models.PROTECT, related_name="+", )
    admission_academic_year = models.ForeignKey('academic_calendar.AcademicYear', on_delete=models.PROTECT, related_name="+", )
    admission_category = models.ForeignKey('common_reference.AdmissionCategory', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    admission_date = models.DateField()
    admission_semester = models.ForeignKey('academic_calendar.Semester', on_delete=models.PROTECT, related_name="+", )
    expected_completion_date = models.DateField(null=True, blank=True)
    class EnrolmentStatus(models.TextChoices):
        ACTIVE = 'ACTIVE'
        ON_BREAK = 'ON_BREAK'
        WITHDRAWN = 'WITHDRAWN'
        TRANSFERRED = 'TRANSFERRED'
        COMPLETED = 'COMPLETED'
        TERMINATED = 'TERMINATED'
    enrolment_status = models.CharField(max_length=11, choices=EnrolmentStatus.choices, default='ACTIVE', db_collation="utf8mb4_unicode_ci")
    class Meta:
        db_table = 'student_programme_enrolment'
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=["enrolment_id", "programme"], name="uq_m7_enrolment_programme"), models.UniqueConstraint(fields=['student', 'programme', 'admission_academic_year'], name='uq_student_programme_enrolment'), models.CheckConstraint(condition=Q(expected_completion_date__isnull=True) | Q(expected_completion_date__gte=F('admission_date')), name='chk_m6_enrolment_completion')]
        indexes = [models.Index(fields=['programme', 'enrolment_status', 'admission_academic_year'], name='ix_m6_enrolment_queue')]

class EnrolmentStatusHistory(Immutable, Validated):
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name="+", )
    occurred_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=30, db_collation="utf8mb4_unicode_ci")
    request_id = models.CharField(max_length=36, db_collation="utf8mb4_unicode_ci")
    sequence_number = models.PositiveBigIntegerField()
    correction_of = models.ForeignKey('admission_enrolment.EnrolmentStatusHistory', on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    enrolment_status_history_id = UnsignedBigAutoField(primary_key=True)
    enrolment = models.ForeignKey('admission_enrolment.StudentProgrammeEnrolment', on_delete=models.PROTECT, related_name="+", )
    class OldStatus(models.TextChoices):
        ACTIVE = 'ACTIVE'
        ON_BREAK = 'ON_BREAK'
        WITHDRAWN = 'WITHDRAWN'
        TRANSFERRED = 'TRANSFERRED'
        COMPLETED = 'COMPLETED'
        TERMINATED = 'TERMINATED'
    old_status = models.CharField(null=True, blank=True, max_length=11, choices=OldStatus.choices, db_collation="utf8mb4_unicode_ci")
    class NewStatus(models.TextChoices):
        ACTIVE = 'ACTIVE'
        ON_BREAK = 'ON_BREAK'
        WITHDRAWN = 'WITHDRAWN'
        TRANSFERRED = 'TRANSFERRED'
        COMPLETED = 'COMPLETED'
        TERMINATED = 'TERMINATED'
    new_status = models.CharField(max_length=11, choices=NewStatus.choices, db_collation="utf8mb4_unicode_ci")
    effective_date = models.DateField()
    reason = models.CharField(max_length=500, db_collation="utf8mb4_unicode_ci")
    class Meta:
        db_table = 'enrolment_status_history'
        default_permissions = ('view',)
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['enrolment', 'sequence_number'], name='uq_m6_history_sequence'), models.CheckConstraint(condition=Q(sequence_number__gt=0), name='chk_m6_history_sequence'), models.CheckConstraint(condition=~Q(reason=''), name='chk_m6_history_reason')]
        indexes = [models.Index(fields=['enrolment', 'effective_date', 'sequence_number'], name='ix_m6_history_asof')]
