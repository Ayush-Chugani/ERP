import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q,F
from django.core.exceptions import ValidationError
from apps.core.fields import UnsignedAutoField
from apps.people_master.fields import UnsignedBigAutoField
from apps.core.models import AppendOnlyQuerySet
from .enums import ResponseType,QuestionnaireType,QuestionnaireStatus,CycleStatus,Visibility
def fk(model,**kw):return models.ForeignKey(model,on_delete=models.PROTECT,related_name='+',**kw)
def token():return str(uuid.uuid4())
class Record(models.Model):
    version=models.PositiveBigIntegerField(default=1)
    actor=fk(settings.AUTH_USER_MODEL)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:abstract=True
    def __str__(self):return str(getattr(self,'questionnaire_name',getattr(self,'cycle_name',getattr(self,'question_text',self.pk))))
class Immutable(models.Model):
    objects=AppendOnlyQuerySet.as_manager()
    class Meta:abstract=True
    def save(self,*a,**kw):
        if not self._state.adding:raise ValidationError('Submitted feedback evidence is immutable.')
        kw['force_insert']=True;super().save(*a,**kw)
    def delete(self,*a,**kw):raise ValidationError('Submitted feedback evidence is immutable.')
    def __str__(self):return self._meta.verbose_name+' '+str(self.pk)
class Category(Record):
    feedback_category_id=UnsignedAutoField(bits=16,primary_key=True)
    institution=fk('organization.Institution')
    category_code=models.CharField(max_length=30,unique=True)
    category_name=models.CharField(max_length=100,unique=True)
    is_active=models.BooleanField(default=True)
    def __str__(self):return self.category_name
    class Meta:db_table='feedback_question_category';ordering=['category_code','pk']
class Question(Record):
    feedback_question_id=UnsignedAutoField(bits=32,primary_key=True)
    feedback_category=fk(Category)
    question_text=models.CharField(max_length=1000)
    response_type=models.CharField(max_length=15,choices=ResponseType.choices)
    is_active=models.BooleanField(default=True)
    rating_min=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    rating_max=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    rating_step=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    text_limit=models.PositiveSmallIntegerField(null=True,blank=True)
    def clean(self):
        if self.response_type=='RATING' and (None in [self.rating_min,self.rating_max,self.rating_step] or self.rating_max<=self.rating_min or self.rating_step<=0):raise ValidationError('Specify a positive rating range and step.')
        if self.response_type=='TEXT' and (not self.text_limit or self.text_limit>10000):raise ValidationError('Text limit must be 1-10000.')
    class Meta:
        db_table='feedback_question';ordering=['pk']
        constraints=[models.CheckConstraint(condition=Q(response_type__in=ResponseType.values),name='chk_m11_response_type')]
class Choice(Record):
    feedback_choice_id=UnsignedAutoField(bits=32,primary_key=True)
    feedback_question=fk(Question)
    choice_text=models.CharField(max_length=250)
    score=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    display_order=models.PositiveSmallIntegerField(null=True,blank=True)
    is_active=models.BooleanField(default=True)
    def __str__(self):return self.choice_text
    class Meta:
        db_table='feedback_choice';ordering=['display_order','pk']
        constraints=[models.UniqueConstraint(fields=['feedback_question','choice_text'],name='uq_feedback_choice')]
class Questionnaire(Record):
    questionnaire_id=UnsignedAutoField(bits=32,primary_key=True)
    institution=fk('organization.Institution')
    questionnaire_code=models.CharField(max_length=30,unique=True)
    questionnaire_name=models.CharField(max_length=150)
    questionnaire_type=models.CharField(max_length=11,choices=QuestionnaireType.choices)
    is_anonymous=models.BooleanField(default=True)
    status=models.CharField(max_length=7,choices=QuestionnaireStatus.choices,default='DRAFT')
    class Meta:
        db_table='feedback_questionnaire';ordering=['pk']
        constraints=[models.CheckConstraint(condition=Q(status__in=QuestionnaireStatus.values),name='chk_m11_questionnaire_state'),models.CheckConstraint(condition=Q(questionnaire_type__in=QuestionnaireType.values),name='chk_m11_questionnaire_type')]
        permissions=[('manage_question_bank','Manage feedback bank'),('manage_questionnaires','Manage questionnaires'),('manage_cycles','Manage feedback cycles'),('submit_feedback','Submit eligible feedback'),('view_admin_results','View administrative aggregates'),('view_faculty_results','View own teaching aggregates'),('export_results','Export aggregates'),('override_cycle_state','Open feedback early'),('view_text_feedback','Review deidentified feedback text')]
class QuestionnaireItem(models.Model):
    questionnaire_item_id=UnsignedBigAutoField(primary_key=True)
    questionnaire=fk(Questionnaire)
    feedback_question=fk(Question)
    weightage=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    display_order=models.PositiveSmallIntegerField()
    is_required=models.BooleanField(default=True)
    def __str__(self):return str(self.questionnaire_id)+' / '+str(self.display_order)
    class Meta:
        db_table='feedback_questionnaire_item';ordering=['display_order','pk']
        constraints=[models.UniqueConstraint(fields=['questionnaire','feedback_question'],name='uq_questionnaire_question'),models.UniqueConstraint(fields=['questionnaire','display_order'],name='uq_m11_question_order'),models.CheckConstraint(condition=Q(weightage__isnull=True)|Q(weightage__gte=0),name='chk_m11_weight')]
class Cycle(Record):
    feedback_cycle_id=UnsignedBigAutoField(primary_key=True)
    questionnaire=fk(Questionnaire)
    academic_term=fk('academic_calendar.AcademicTerm')
    programme=fk('organization.Programme',null=True,blank=True)
    cycle_name=models.CharField(max_length=150)
    start_at=models.DateTimeField()
    end_at=models.DateTimeField()
    result_visibility=models.CharField(max_length=10,choices=Visibility.choices,default='HIDDEN')
    status=models.CharField(max_length=9,choices=CycleStatus.choices,default='SCHEDULED')
    minimum_cohort=models.PositiveSmallIntegerField()
    allow_text_review=models.BooleanField()
    target_policy=models.CharField(max_length=20,choices=[(v,v) for v in ['ENROLLED','COMPLETING','EXPLICIT']])
    explicit_registrations=models.JSONField(default=list,blank=True)
    frozen=models.JSONField(default=dict,blank=True)
    key_fingerprint=models.CharField(max_length=64,blank=True)
    def clean(self):
        if self.start_at and self.end_at and self.end_at<=self.start_at:raise ValidationError('End must follow start.')
        if self.minimum_cohort is not None and self.minimum_cohort<2:raise ValidationError('Privacy threshold cannot permit singleton reports.')
    class Meta:
        db_table='feedback_cycle';ordering=['-start_at','pk']
        constraints=[models.CheckConstraint(condition=Q(end_at__gt=F('start_at')),name='chk_feedback_cycle_dates'),models.CheckConstraint(condition=Q(status__in=CycleStatus.values),name='chk_m11_cycle_state'),models.CheckConstraint(condition=Q(result_visibility__in=Visibility.values),name='chk_m11_visibility'),models.CheckConstraint(condition=Q(minimum_cohort__gte=2),name='chk_m11_cohort')]
        indexes=[models.Index(fields=['academic_term','status','start_at','end_at'],name='ix_m11_cycle_window')]
class Response(Immutable):
    feedback_response_id=UnsignedBigAutoField(primary_key=True)
    feedback_cycle=fk(Cycle)
    term_registration=fk('term_registration.StudentTermRegistration',null=True,blank=True)
    course_offering=fk('term_registration.CourseOffering',null=True,blank=True)
    faculty_assignment=fk('teaching_timetable.FacultyAssignment',null=True,blank=True)
    target_key=models.CharField(max_length=80)
    submitted_at=models.DateTimeField(auto_now_add=True)
    response_token=models.CharField(max_length=36,unique=True,default=token)
    class Meta:
        db_table='feedback_response';ordering=['pk']
        indexes=[models.Index(fields=['feedback_cycle','target_key'],name='ix_m11_response_target')]
class ResponseItem(Immutable):
    feedback_response_item_id=UnsignedBigAutoField(primary_key=True)
    feedback_response=fk(Response)
    questionnaire_item=fk(QuestionnaireItem)
    feedback_choice=fk(Choice,null=True,blank=True)
    numeric_score=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    text_response=models.TextField(null=True,blank=True)
    class Meta:
        db_table='feedback_response_item';ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['feedback_response','questionnaire_item'],name='uq_feedback_response_item')]
class ResponseItemChoice(Immutable):
    feedback_response_item=fk(ResponseItem)
    feedback_choice=fk(Choice)
    class Meta:
        db_table='feedback_response_item_choice';ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['feedback_response_item','feedback_choice'],name='uq_m11_multiple_choice')]
class SubmissionLedger(Immutable):
    cycle=fk(Cycle)
    fingerprint=models.CharField(max_length=64)
    request_digest=models.CharField(max_length=64)
    receipt=models.CharField(max_length=36,default=token,unique=True)
    class Meta:
        db_table='platform_m11_ledger'
        constraints=[models.UniqueConstraint(fields=['cycle','fingerprint'],name='uq_m11_once')]
class Audit(Immutable):
    institution=fk('organization.Institution')
    actor=fk(settings.AUTH_USER_MODEL)
    action=models.CharField(max_length=60)
    resource=models.CharField(max_length=40)
    record_id=models.PositiveBigIntegerField()
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    reason=models.CharField(max_length=500)
    request_key=models.CharField(max_length=100)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:db_table='platform_m11_audit';ordering=['pk']
class CommandReceipt(Immutable):
    actor=fk(settings.AUTH_USER_MODEL)
    key=models.CharField(max_length=100)
    digest=models.CharField(max_length=64)
    result=models.JSONField()
    class Meta:
        db_table='platform_m11_command'
        constraints=[models.UniqueConstraint(fields=['actor','key'],name='uq_m11_command')]
