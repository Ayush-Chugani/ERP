from django.conf import settings
from django.db import models
from django.db.models import Q, F, Value, Case, When
from django.db.models.functions import Coalesce
from apps.people_master.fields import UnsignedBigAutoField
from .support import ProgressionApproval, RegistrationAudit, RegistrationPolicy, CommandReceipt, RegistrationEvent, EventDelivery


def parent(model, **kwargs):
    return models.ForeignKey(model, on_delete=models.PROTECT, related_name='+', **kwargs)


def text(length, **kwargs):
    return models.CharField(max_length=length, db_collation='utf8mb4_unicode_ci', **kwargs)


class Record(models.Model):
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = parent(settings.AUTH_USER_MODEL)
    updated_by = parent(settings.AUTH_USER_MODEL)

    class Meta:
        abstract = True

    def clean(self):
        from .validation import clean_record
        clean_record(self)


class OfferingStatus(models.TextChoices):
    PLANNED='PLANNED'
    REGISTRATION_OPEN='REGISTRATION_OPEN'
    ACTIVE='ACTIVE'
    COMPLETED='COMPLETED'
    CANCELLED='CANCELLED'


class SessionType(models.TextChoices):
    LECTURE='LECTURE'
    TUTORIAL='TUTORIAL'
    PRACTICAL='PRACTICAL'
    PROJECT='PROJECT'
    SEMINAR='SEMINAR'
    OTHER='OTHER'


class ProgrammeTermOffering(Record):
    programme_term_offering_id=UnsignedBigAutoField(primary_key=True)
    academic_term=parent('academic_calendar.AcademicTerm')
    programme=parent('organization.Programme')
    specialization=parent('organization.ProgrammeSpecialization',null=True,blank=True)
    specialization_key=models.GeneratedField(expression=Coalesce('specialization',Value(0)),output_field=models.PositiveSmallIntegerField(),db_persist=True)
    curriculum_scheme=parent('curriculum_catalog.CurriculumScheme')
    semester=parent('academic_calendar.Semester')
    status=text(17,choices=OfferingStatus.choices,default=OfferingStatus.PLANNED)

    class Meta:
        db_table='programme_term_offering'
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['academic_term','programme','specialization_key','semester'],name='uq_programme_term'),models.UniqueConstraint(fields=['programme_term_offering_id','programme'],name='uq_m7_offering_programme'),models.CheckConstraint(condition=Q(status__in=OfferingStatus.values),name='chk_m7_offering_status')]
        permissions=[('view_registration','View scoped registration workspace'),('approve_progression','Approve term progression with reason'),('manage_registration','Manage registration setup and allocations'),('approve_registration','Approve registrations'),('export_registration','Export scoped registration records')]


class ClassSection(Record):
    class_section_id=UnsignedBigAutoField(primary_key=True)
    programme_term_offering=parent(ProgrammeTermOffering)
    section_code=text(20)
    section_name=text(100,null=True,blank=True)
    capacity=models.PositiveSmallIntegerField(null=True,blank=True)
    home_room=parent('organization.Room',null=True,blank=True)
    is_active=models.BooleanField(default=True)

    class Meta:
        db_table='class_section'
        ordering=['section_code','pk']
        constraints=[models.UniqueConstraint(fields=['programme_term_offering','section_code'],name='uq_class_section'),models.UniqueConstraint(fields=['class_section_id','programme_term_offering'],name='uq_class_section_owner'),models.CheckConstraint(condition=Q(capacity__isnull=True)|Q(capacity__gt=0),name='chk_m7_section_capacity')]


class ClassBatch(Record):
    class_batch_id=UnsignedBigAutoField(primary_key=True)
    class_section=parent(ClassSection)
    batch_code=text(20)
    batch_name=text(100,null=True,blank=True)
    capacity=models.PositiveSmallIntegerField(null=True,blank=True)
    is_active=models.BooleanField(default=True)

    class Meta:
        db_table='class_batch'
        ordering=['batch_code','pk']
        constraints=[models.UniqueConstraint(fields=['class_section','batch_code'],name='uq_class_batch'),models.UniqueConstraint(fields=['class_batch_id','class_section'],name='uq_class_batch_owner'),models.CheckConstraint(condition=Q(capacity__isnull=True)|Q(capacity__gt=0),name='chk_m7_batch_capacity')]


class TermStatus(models.TextChoices):
    DRAFT='DRAFT'
    REGISTERED='REGISTERED'
    APPROVED='APPROVED'
    CANCELLED='CANCELLED'
    COMPLETED='COMPLETED'


class StudentTermRegistration(Record):
    term_registration_id=UnsignedBigAutoField(primary_key=True)
    enrolment=parent('admission_enrolment.StudentProgrammeEnrolment')
    programme_term_offering=parent(ProgrammeTermOffering)
    programme=parent('organization.Programme',editable=False)
    class_section=parent(ClassSection,null=True,blank=True)
    class_batch=parent(ClassBatch,null=True,blank=True)
    roll_number=text(30,null=True,blank=True)
    registration_date=models.DateField()
    registration_status=text(10,choices=TermStatus.choices,default=TermStatus.DRAFT)

    class Meta:
        db_table='student_term_registration'
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['enrolment','programme_term_offering'],name='uq_student_term_registration'),models.UniqueConstraint(fields=['programme_term_offering','roll_number'],name='uq_term_roll'),models.UniqueConstraint(fields=['term_registration_id','programme_term_offering'],name='uq_m7_term_registration_owner'),models.CheckConstraint(condition=Q(class_batch__isnull=True)|Q(class_section__isnull=False),name='chk_term_registration_batch_section'),models.CheckConstraint(condition=Q(registration_status__in=TermStatus.values),name='chk_m7_term_status')]
        indexes=[models.Index(fields=['class_section','registration_status'],name='ix_m7_section_seats'),models.Index(fields=['class_batch','registration_status'],name='ix_m7_batch_seats')]


class CourseStatus(models.TextChoices):
    PLANNED='PLANNED'
    OPEN='OPEN'
    ACTIVE='ACTIVE'
    COMPLETED='COMPLETED'
    CANCELLED='CANCELLED'


class CourseOffering(Record):
    course_offering_id=UnsignedBigAutoField(primary_key=True)
    programme_term_offering=parent(ProgrammeTermOffering)
    curriculum_course=parent('curriculum_catalog.CurriculumCourse',null=True,blank=True)
    course=parent('curriculum_catalog.CourseCatalog')
    offering_code=text(50,unique=True)
    registration_capacity=models.PositiveSmallIntegerField(null=True,blank=True)
    status=text(9,choices=CourseStatus.choices,default=CourseStatus.PLANNED)

    class Meta:
        db_table='course_offering'
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['programme_term_offering','course'],name='uq_course_offering'),models.UniqueConstraint(fields=['course_offering_id','programme_term_offering'],name='uq_course_offering_owner'),models.CheckConstraint(condition=Q(registration_capacity__isnull=True)|Q(registration_capacity__gt=0),name='chk_m7_course_capacity'),models.CheckConstraint(condition=Q(status__in=CourseStatus.values),name='chk_m7_course_status')]


class CourseOfferingSection(Record):
    course_offering_section_id=UnsignedBigAutoField(primary_key=True)
    course_offering=parent(CourseOffering)
    programme_term_offering=parent(ProgrammeTermOffering,editable=False)
    class_section=parent(ClassSection)
    class_batch=parent(ClassBatch,null=True,blank=True)
    class_batch_key=models.GeneratedField(expression=Coalesce('class_batch',Value(0)),output_field=models.PositiveBigIntegerField(),db_persist=True)
    session_type=text(9,choices=SessionType.choices)

    class Meta:
        db_table='course_offering_section'
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['course_offering','class_section','class_batch_key','session_type'],name='uq_course_offering_section'),models.UniqueConstraint(fields=['course_offering_section_id','course_offering'],name='uq_course_offering_section_course'),models.UniqueConstraint(fields=['course_offering_section_id','programme_term_offering'],name='uq_course_offering_section_owner'),models.UniqueConstraint(fields=['course_offering_section_id','session_type'],name='uq_m7_mapping_session'),models.CheckConstraint(condition=Q(session_type__in=SessionType.values),name='chk_m7_mapping_session')]


class RegistrationType(models.TextChoices):
    REGULAR='REGULAR'
    ELECTIVE='ELECTIVE'
    BACKLOG='BACKLOG'
    REPEAT='REPEAT'
    IMPROVEMENT='IMPROVEMENT'
    AUDIT='AUDIT'
    CREDIT_TRANSFER='CREDIT_TRANSFER'


class RegistrationStatus(models.TextChoices):
    REGISTERED='REGISTERED'
    APPROVED='APPROVED'
    DROPPED='DROPPED'
    WITHDRAWN='WITHDRAWN'
    COMPLETED='COMPLETED'


class StudentCourseRegistration(Record):
    course_registration_id=UnsignedBigAutoField(primary_key=True)
    term_registration=parent(StudentTermRegistration)
    course_offering=parent(CourseOffering)
    programme_term_offering=parent(ProgrammeTermOffering,editable=False)
    registration_type=text(15,choices=RegistrationType.choices,default=RegistrationType.REGULAR)
    registration_date=models.DateField()
    registration_status=text(10,choices=RegistrationStatus.choices,default=RegistrationStatus.REGISTERED)

    class Meta:
        db_table='student_course_registration'
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['term_registration','course_offering'],name='uq_student_course_registration'),models.UniqueConstraint(fields=['course_registration_id','course_offering'],name='uq_course_registration_owner'),models.CheckConstraint(condition=Q(registration_type__in=RegistrationType.values),name='chk_m7_registration_type'),models.CheckConstraint(condition=Q(registration_status__in=RegistrationStatus.values),name='chk_m7_registration_status')]
        indexes=[models.Index(fields=['course_offering','registration_status'],name='ix_m7_course_seats')]


class RosterStatus(models.TextChoices):
    ACTIVE='ACTIVE'
    DROPPED='DROPPED'
    TRANSFERRED='TRANSFERRED'
    COMPLETED='COMPLETED'


class CourseOfferingSectionStudent(Record):
    course_offering_section_student_id=UnsignedBigAutoField(primary_key=True)
    course_offering_section=parent(CourseOfferingSection)
    course_registration=parent(StudentCourseRegistration)
    course_offering=parent(CourseOffering,editable=False)
    session_type=text(9,choices=SessionType.choices,editable=False)
    roster_status=text(11,choices=RosterStatus.choices,default=RosterStatus.ACTIVE)
    effective_from=models.DateField()
    effective_to=models.DateField(null=True,blank=True)
    active_registration_key=models.GeneratedField(expression=Case(When(roster_status='ACTIVE',then=F('course_registration')),default=Value(None)),output_field=models.PositiveBigIntegerField(null=True),db_persist=True,null=True)

    class Meta:
        db_table='course_offering_section_student'
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['course_offering_section','course_registration','effective_from'],name='uq_course_section_student'),models.UniqueConstraint(fields=['course_offering_section_student_id','course_offering_section'],name='uq_course_section_student_owner'),models.UniqueConstraint(fields=['active_registration_key','session_type'],name='uq_m7_active_roster_session'),models.CheckConstraint(condition=Q(effective_to__isnull=True)|Q(effective_to__gt=F('effective_from')),name='chk_course_section_student_dates'),models.CheckConstraint(condition=~Q(roster_status='ACTIVE')|Q(effective_to__isnull=True),name='chk_m7_roster_open'),models.CheckConstraint(condition=Q(roster_status__in=RosterStatus.values),name='chk_m7_roster_status')]
        indexes=[models.Index(fields=['course_offering_section','roster_status','effective_from','effective_to'],name='ix_m7_roster_current')]
