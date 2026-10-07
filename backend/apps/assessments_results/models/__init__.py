from django.conf import settings
from django.db import models
from django.db.models import Q,F
from apps.people_master.fields import UnsignedBigAutoField,UnsignedTinyIntegerField
from apps.core.fields import UnsignedAutoField
from apps.core.models import AppendOnlyQuerySet
from django.core.exceptions import ValidationError

def fk(model,**kw):return models.ForeignKey(model,on_delete=models.PROTECT,related_name='+',**kw)
def money(**kw):return models.DecimalField(max_digits=7,decimal_places=2,**kw)
def choices(values):return [(v,v) for v in values.split()]
RESULTS='PASS FAIL ABSENT WITHHELD EXEMPTED INCOMPLETE'
class Record(models.Model):
    version=models.PositiveBigIntegerField(default=1)
    actor=fk(settings.AUTH_USER_MODEL)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:abstract=True
class Evidence(models.Model):
    objects=AppendOnlyQuerySet.as_manager()
    class Meta:abstract=True
    def save(self,*a,**kw):
        if not self._state.adding:raise ValidationError('Result evidence is immutable.')
        kw['force_insert']=True;super().save(*a,**kw)
    def delete(self,*a,**kw):raise ValidationError('Result evidence is immutable.')
class AssessmentComponent(Record):
    assessment_component_id=UnsignedBigAutoField(primary_key=True)
    course_offering=fk('term_registration.CourseOffering')
    component_code=models.CharField(max_length=30)
    component_name=models.CharField(max_length=100)
    component_type=models.CharField(max_length=20,choices=choices('INTERNAL_TEST QUIZ ASSIGNMENT LAB PROJECT PRESENTATION TERM_WORK OTHER'))
    maximum_marks=money()
    weightage_percent=models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True)
    is_mandatory=models.BooleanField(default=True)
    def __str__(self):return self.component_code+' / '+self.component_name
    class Meta:
        db_table='assessment_component'
        constraints=[models.UniqueConstraint(fields=['course_offering','component_code'],name='uq_assessment_component'),models.UniqueConstraint(fields=['assessment_component_id','course_offering'],name='uq_assessment_component_owner'),models.CheckConstraint(condition=Q(maximum_marks__gt=0),name='chk_m10_component_max'),models.CheckConstraint(condition=Q(weightage_percent__isnull=True)|Q(weightage_percent__gte=0,weightage_percent__lte=100),name='chk_m10_component_weight')]
        permissions=[(p+'_assessment',label) for p,label in [('view','View assessments'),('configure','Configure assessment policy and setup'),('mark','Enter assigned marks'),('calculate','Calculate academic results'),('publish','Review and publish results'),('correct','Reopen and withhold results'),('export','Export academic results')]]
class GradeScale(Evidence):
    grade_scale_id=UnsignedAutoField(bits=16,primary_key=True)
    institution=fk('organization.Institution')
    scale_name=models.CharField(max_length=100,unique=True)
    effective_from=models.DateField()
    effective_to=models.DateField(null=True,blank=True)
    is_active=models.BooleanField(default=True)
    actor=fk(settings.AUTH_USER_MODEL)
    class Meta:
        db_table='grade_scale'
        constraints=[models.CheckConstraint(condition=Q(effective_to__isnull=True)|Q(effective_to__gte=F('effective_from')),name='chk_m10_scale_dates')]
class GradeRule(Evidence):
    grade_rule_id=UnsignedAutoField(bits=32,primary_key=True)
    grade_scale=fk(GradeScale)
    grade_letter=models.CharField(max_length=5)
    grade_point=models.DecimalField(max_digits=4,decimal_places=2)
    minimum_percentage=models.DecimalField(max_digits=5,decimal_places=2)
    maximum_percentage=models.DecimalField(max_digits=5,decimal_places=2)
    result_status=models.CharField(max_length=8,choices=choices('PASS FAIL ABSENT WITHHELD EXEMPTED'))
    class Meta:
        db_table='grade_rule'
        constraints=[models.UniqueConstraint(fields=['grade_scale','grade_letter'],name='uq_grade_rule'),models.CheckConstraint(condition=Q(minimum_percentage__gte=0,maximum_percentage__lte=100,maximum_percentage__gt=F('minimum_percentage'),grade_point__gte=0),name='chk_m10_grade_range')]
class CalculationPolicy(Evidence):
    course_offering=fk('term_registration.CourseOffering')
    number=models.PositiveIntegerField()
    grade_scale=fk(GradeScale)
    rules=models.JSONField()
    actor=fk(settings.AUTH_USER_MODEL)
    reason=models.CharField(max_length=500)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m10_policy'
        constraints=[models.UniqueConstraint(fields=['course_offering','number'],name='uq_m10_policy_revision')]
class AssessmentEvent(Record):
    assessment_event_id=UnsignedBigAutoField(primary_key=True)
    assessment_component=fk(AssessmentComponent)
    course_offering=fk('term_registration.CourseOffering')
    policy=fk(CalculationPolicy)
    attempt_number=models.PositiveSmallIntegerField()
    event_number=models.PositiveSmallIntegerField(null=True,blank=True)
    event_title=models.CharField(max_length=150)
    assessment_date=models.DateField()
    start_time=models.TimeField(null=True,blank=True)
    end_time=models.TimeField(null=True,blank=True)
    maximum_marks=money()
    reduced_maximum_marks=money(null=True,blank=True)
    details=models.TextField(blank=True)
    status=models.CharField(max_length=9,choices=choices('PLANNED CONDUCTED CANCELLED PUBLISHED'),default='PLANNED')
    roster=models.JSONField(default=list,blank=True)
    class Meta:
        db_table='assessment_event'
        constraints=[models.CheckConstraint(condition=Q(status__in=['PLANNED','CONDUCTED','CANCELLED','PUBLISHED']),name='chk_m10_event_status'),models.UniqueConstraint(fields=['assessment_event_id','course_offering'],name='uq_assessment_event_owner'),models.CheckConstraint(condition=Q(maximum_marks__gt=0)&(Q(reduced_maximum_marks__isnull=True)|Q(reduced_maximum_marks__gt=0,reduced_maximum_marks__lte=F('maximum_marks'))),name='chk_m10_event_marks'),models.CheckConstraint(condition=Q(start_time__isnull=True)|Q(end_time__isnull=True)|Q(end_time__gt=F('start_time')),name='chk_m10_event_time'),models.CheckConstraint(condition=Q(attempt_number__gte=1,attempt_number__lte=255),name='chk_m10_event_attempt')]
        indexes=[models.Index(fields=['course_offering','assessment_date','status'],name='ix_m10_offering_events')]
class StudentAssessmentMark(Record):
    student_assessment_mark_id=UnsignedBigAutoField(primary_key=True)
    assessment_event=fk(AssessmentEvent)
    course_registration=fk('term_registration.StudentCourseRegistration')
    course_offering=fk('term_registration.CourseOffering')
    attendance_status=models.CharField(max_length=11,choices=choices('PRESENT ABSENT EXEMPTED MALPRACTICE'))
    marks_obtained=money(null=True,blank=True)
    reduced_marks=money(null=True,blank=True)
    remarks=models.CharField(max_length=500,blank=True)
    evaluated_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        db_table='student_assessment_mark'
        constraints=[models.CheckConstraint(condition=Q(attendance_status__in=['PRESENT','ABSENT','EXEMPTED','MALPRACTICE']),name='chk_m10_mark_status'),models.UniqueConstraint(fields=['assessment_event','course_registration'],name='uq_student_assessment'),models.CheckConstraint(condition=Q(marks_obtained__isnull=True)|Q(marks_obtained__gte=0),name='chk_m10_mark_raw'),models.CheckConstraint(condition=Q(reduced_marks__isnull=True)|Q(reduced_marks__gte=0),name='chk_m10_mark_reduced')]
class StudentCourseResult(Record):
    student_course_result_id=UnsignedBigAutoField(primary_key=True)
    course_registration=fk('term_registration.StudentCourseRegistration')
    attempt_number=UnsignedTinyIntegerField(default=1)
    internal_marks=money(null=True,blank=True)
    external_marks=money(null=True,blank=True)
    total_marks=money(null=True,blank=True)
    grade_letter=models.CharField(max_length=5,blank=True)
    grade_point=models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    credits_earned=models.DecimalField(max_digits=4,decimal_places=1,default=0)
    result_status=models.CharField(max_length=10,choices=choices(RESULTS))
    result_date=models.DateField(null=True,blank=True)
    remarks=models.CharField(max_length=500,blank=True)
    policy=fk(CalculationPolicy)
    evidence=models.JSONField()
    is_withheld=models.BooleanField(default=False)
    state=models.CharField(max_length=10,default='CALCULATED',choices=choices('CALCULATED PUBLISHED WITHHELD'))
    class Meta:
        db_table='student_course_result'
        constraints=[models.CheckConstraint(condition=Q(result_status__in=RESULTS.split()),name='chk_m10_course_status'),models.CheckConstraint(condition=Q(state__in=['CALCULATED','PUBLISHED','WITHHELD']),name='chk_m10_course_state'),models.UniqueConstraint(fields=['course_registration','attempt_number'],name='uq_course_result_attempt'),models.CheckConstraint(condition=Q(attempt_number__gte=1,attempt_number__lte=255,credits_earned__gte=0),name='chk_m10_course_result')]
class StudentTermResult(Record):
    student_term_result_id=UnsignedBigAutoField(primary_key=True)
    term_registration=models.OneToOneField('term_registration.StudentTermRegistration',on_delete=models.PROTECT)
    credits_registered=models.DecimalField(max_digits=6,decimal_places=1,default=0)
    credits_earned=models.DecimalField(max_digits=6,decimal_places=1,default=0)
    sgpa=models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    cgpa=models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    result_status=models.CharField(max_length=10,choices=choices('PASS FAIL PROMOTED WITHHELD INCOMPLETE'))
    published_at=models.DateTimeField(null=True,blank=True)
    is_withheld=models.BooleanField(default=False)
    state=models.CharField(max_length=10,default='CALCULATED',choices=choices('CALCULATED PUBLISHED WITHHELD'))
    evidence=models.JSONField()
    class Meta:
        db_table='student_term_result'
        constraints=[models.CheckConstraint(condition=Q(result_status__in=['PASS','FAIL','PROMOTED','WITHHELD','INCOMPLETE']),name='chk_m10_term_status'),models.CheckConstraint(condition=Q(credits_registered__gte=0,credits_earned__gte=0,credits_earned__lte=F('credits_registered')),name='chk_m10_term_credits'),models.CheckConstraint(condition=Q(state__in=['CALCULATED','PUBLISHED','WITHHELD']),name='chk_m10_term_state')]
class Publication(Evidence):
    institution=fk('organization.Institution')
    resource=models.CharField(max_length=30)
    record_id=models.PositiveBigIntegerField()
    number=models.PositiveIntegerField()
    data=models.JSONField()
    actor=fk(settings.AUTH_USER_MODEL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m10_publication'
        constraints=[models.UniqueConstraint(fields=['resource','record_id','number'],name='uq_m10_publication')]
class Audit(Evidence):
    institution=fk('organization.Institution')
    course_offering=fk('term_registration.CourseOffering',null=True)
    actor=fk(settings.AUTH_USER_MODEL)
    authority=models.JSONField()
    action=models.CharField(max_length=50)
    resource=models.CharField(max_length=30)
    record_id=models.PositiveBigIntegerField()
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    reason=models.CharField(max_length=500)
    request_key=models.CharField(max_length=100)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='platform_m10_audit'
        indexes=[models.Index(fields=['resource','record_id','id'],name='ix_m10_audit_object')]
class Receipt(Evidence):
    actor=fk(settings.AUTH_USER_MODEL)
    key=models.CharField(max_length=100)
    digest=models.CharField(max_length=64)
    result=models.JSONField()
    class Meta:
        db_table='platform_m10_receipt'
        constraints=[models.UniqueConstraint(fields=['actor','key'],name='uq_m10_receipt')]
