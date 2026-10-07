"""M9 domain tables and immutable supporting evidence."""
from django.conf import settings
from django.db import models
from django.db.models import Q,F,Case,When,Value
from django.core.exceptions import ValidationError
from apps.core.fields import UnsignedAutoField
from apps.people_master.fields import UnsignedBigAutoField
from apps.core.models import AppendOnlyQuerySet

def parent(model,**kwargs):
    return models.ForeignKey(model,on_delete=models.PROTECT,related_name='+',**kwargs)

class Immutable(models.Model):
    objects=AppendOnlyQuerySet.as_manager()
    class Meta:
        abstract=True
        default_permissions=('view',)
    def save(self,*args,**kwargs):
        if not self._state.adding: raise ValidationError('Attendance evidence is immutable.')
        kwargs['force_insert']=True
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError('Attendance evidence is immutable.')

class AttendanceStatus(Immutable):
    attendance_status_id=UnsignedAutoField(bits=8,primary_key=True)
    status_code=models.CharField(max_length=20,unique=True)
    status_name=models.CharField(max_length=50,unique=True)
    counts_as_present=models.BooleanField(default=False)
    is_active=models.BooleanField(default=True)
    class Meta:
        db_table='attendance_status'
        default_permissions=('view',)

class PolicyRevision(Immutable):
    section=parent('term_registration.CourseOfferingSection')
    number=models.PositiveIntegerField()
    basis=models.CharField(max_length=8,choices=[('SESSION','Session'),('DURATION','Duration')])
    rules=models.JSONField()
    threshold=models.DecimalField(max_digits=5,decimal_places=2)
    edit_days=models.PositiveSmallIntegerField()
    correction_days=models.PositiveSmallIntegerField()
    reason=models.CharField(max_length=500)
    actor=parent(settings.AUTH_USER_MODEL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m9_policy'
        constraints=[models.UniqueConstraint(fields=['section','number'],name='uq_m9_policy_number'),models.CheckConstraint(condition=Q(threshold__gte=0,threshold__lte=100),name='chk_m9_threshold'),models.CheckConstraint(condition=Q(basis__in=['SESSION','DURATION']),name='chk_m9_basis')]
        permissions=[('configure_attendance','Configure section attendance policy')]

class ClassSession(models.Model):
    class_session_id=UnsignedBigAutoField(primary_key=True)
    course_offering_section=parent('term_registration.CourseOfferingSection')
    faculty_assignment=parent('teaching_timetable.FacultyAssignment')
    timetable_session=parent('teaching_timetable.TimetableSession',null=True,blank=True)
    occurrence=models.OneToOneField('teaching_timetable.PublishedOccurrence',on_delete=models.PROTECT,null=True,blank=True)
    occurrence_sequence=models.PositiveIntegerField(default=0)
    source_session=parent('self',null=True,blank=True)
    session_date=models.DateField()
    start_time=models.TimeField()
    end_time=models.TimeField()
    room=parent('organization.Room')
    session_type=models.CharField(max_length=9,db_collation='utf8mb4_unicode_ci')
    planned_topic=models.TextField(blank=True)
    topic_covered=models.TextField(blank=True)
    class_number=models.PositiveSmallIntegerField()
    session_status=models.CharField(max_length=11,default='PLANNED',choices=[(v,v) for v in ['PLANNED','CONDUCTED','CANCELLED','RESCHEDULED']])
    register_status=models.CharField(max_length=9,default='UNOPENED',choices=[(v,v) for v in ['UNOPENED','OPEN','FINALIZED','REOPENED']])
    policy=parent(PolicyRevision)
    version=models.PositiveBigIntegerField(default=1)
    created_by=parent(settings.AUTH_USER_MODEL)
    updated_by=parent(settings.AUTH_USER_MODEL)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    finalized_at=models.DateTimeField(null=True,blank=True)
    calendar_reference=models.CharField(max_length=200)
    class Meta:
        db_table='class_session'
        ordering=['session_date','start_time','pk']
        constraints=[
            models.UniqueConstraint(fields=['course_offering_section','session_date','start_time'],name='uq_class_session'),
            models.UniqueConstraint(fields=['class_session_id','course_offering_section'],name='uq_class_session_owner'),
            models.UniqueConstraint(fields=['course_offering_section','class_number'],name='uq_m9_class_number'),
            models.CheckConstraint(condition=Q(end_time__gt=F('start_time')),name='chk_class_session_time'),
            models.CheckConstraint(condition=Q(session_status__in=['PLANNED','CONDUCTED','CANCELLED','RESCHEDULED']),name='chk_m9_session_status'),
            models.CheckConstraint(condition=Q(register_status__in=['UNOPENED','OPEN','FINALIZED','REOPENED']),name='chk_m9_register_status')]
        indexes=[models.Index(fields=['course_offering_section','session_date','register_status'],name='ix_m9_section_date')]
        default_permissions=('view',)
        permissions=[('view_attendance','View scoped registers'),('manage_attendance','Manage sessions and lesson plans'),('mark_attendance','Mark and finalize assigned registers'),('review_attendance','Review corrections'),('reopen_attendance','Reopen finalized registers'),('exceptional_attendance','Create exceptional sessions'),('export_attendance','Export scoped attendance')]

class StudentAttendance(models.Model):
    attendance_id=UnsignedBigAutoField(primary_key=True)
    class_session=parent(ClassSession)
    course_offering_section_student=parent('term_registration.CourseOfferingSectionStudent')
    course_offering_section=parent('term_registration.CourseOfferingSection')
    student=parent('people_master.Student')
    attendance_status=parent(AttendanceStatus,null=True,blank=True)
    marked_at=models.DateTimeField(null=True,blank=True)
    marked_by_user=parent(settings.AUTH_USER_MODEL,null=True,blank=True)
    remarks=models.CharField(max_length=500,blank=True)
    is_eligible=models.BooleanField(default=True)
    exclusion_reason=models.CharField(max_length=500,blank=True)
    version=models.PositiveBigIntegerField(default=1)
    credit=models.DecimalField(max_digits=12,decimal_places=4,null=True,blank=True)
    denominator=models.DecimalField(max_digits=12,decimal_places=4,null=True,blank=True)
    class Meta:
        db_table='student_attendance'
        default_permissions=('view',)
        constraints=[models.UniqueConstraint(fields=['class_session','course_offering_section_student'],name='uq_m9_attendance_roster'),models.UniqueConstraint(fields=['class_session','student'],name='uq_m9_attendance_student'),models.CheckConstraint(condition=Q(credit__isnull=True,denominator__isnull=True)|Q(credit__gte=0,denominator__gte=F('credit')),name='chk_m9_contribution')]
        indexes=[models.Index(fields=['student','class_session'],name='ix_m9_student_session')]

class CorrectionRequest(models.Model):
    attendance_correction_id=UnsignedBigAutoField(primary_key=True)
    attendance=parent(StudentAttendance)
    old_status=parent(AttendanceStatus)
    requested_status=parent(AttendanceStatus)
    attendance_version=models.PositiveBigIntegerField()
    reason=models.CharField(max_length=1000)
    evidence_reference=models.CharField(max_length=200,blank=True)
    request_status=models.CharField(max_length=9,default='PENDING')
    requested_by=parent(settings.AUTH_USER_MODEL)
    resolved_by=parent(settings.AUTH_USER_MODEL,null=True,blank=True)
    resolution_remarks=models.CharField(max_length=1000,blank=True)
    requested_at=models.DateTimeField(auto_now_add=True)
    resolved_at=models.DateTimeField(null=True,blank=True)
    version=models.PositiveBigIntegerField(default=1)
    pending_key=models.GeneratedField(expression=Case(When(request_status='PENDING',then=F('attendance')),default=Value(None)),output_field=models.PositiveBigIntegerField(null=True),db_persist=True,null=True,unique=True)
    class Meta:
        db_table='attendance_correction_request'
        default_permissions=('view',)
        constraints=[models.CheckConstraint(condition=Q(request_status__in=['PENDING','APPROVED','REJECTED','CANCELLED']),name='chk_m9_correction_state')]
        indexes=[models.Index(fields=['request_status','requested_at'],name='ix_m9_correction_queue')]

class LessonRevision(Immutable):
    section=parent('term_registration.CourseOfferingSection')
    number=models.PositiveIntegerField()
    topics=models.JSONField()
    actor=parent(settings.AUTH_USER_MODEL)
    reason=models.CharField(max_length=500)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m9_lesson_revision'
        constraints=[models.UniqueConstraint(fields=['section','number'],name='uq_m9_lesson_number')]

class TopicCoverage(Immutable):
    session=parent(ClassSession)
    lesson_revision=parent(LessonRevision)
    topic_key=models.CharField(max_length=50)
    percent=models.DecimalField(max_digits=5,decimal_places=2)
    minutes=models.PositiveSmallIntegerField()
    remarks=models.CharField(max_length=500,blank=True)
    actor=parent(settings.AUTH_USER_MODEL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m9_coverage'
        constraints=[models.CheckConstraint(condition=Q(percent__gt=0,percent__lte=100,minutes__gt=0),name='chk_m9_coverage')]

class AuditEvent(Immutable):
    section=parent('term_registration.CourseOfferingSection')
    actor=parent(settings.AUTH_USER_MODEL)
    authority=models.JSONField()
    action=models.CharField(max_length=50)
    resource=models.CharField(max_length=50)
    record_id=models.PositiveBigIntegerField()
    reason=models.CharField(max_length=1000)
    request_key=models.CharField(max_length=100)
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m9_audit'
        indexes=[models.Index(fields=['resource','record_id','id'],name='ix_m9_history')]

class OutboxEvent(Immutable):
    audit=models.OneToOneField(AuditEvent,on_delete=models.PROTECT)
    topic=models.CharField(max_length=80)
    payload=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: db_table='platform_m9_outbox'

class Delivery(Immutable):
    event=parent(OutboxEvent)
    consumer=models.CharField(max_length=80)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m9_delivery'
        constraints=[models.UniqueConstraint(fields=['event','consumer'],name='uq_m9_delivery')]

class CommandReceipt(Immutable):
    actor=parent(settings.AUTH_USER_MODEL)
    key=models.CharField(max_length=100)
    digest=models.CharField(max_length=64)
    result=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m9_receipt'
        constraints=[models.UniqueConstraint(fields=['actor','key'],name='uq_m9_receipt')]
