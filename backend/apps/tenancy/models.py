from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class InstitutionModule(models.Model):
    institution = models.OneToOneField('organization.Institution', on_delete=models.PROTECT)
    organization_structure = models.BooleanField(default=False)
    academic_calendar = models.BooleanField(default=False)
    curriculum_catalog = models.BooleanField(default=False)
    people_master = models.BooleanField(default=False)
    admission_enrolment = models.BooleanField(default=False)
    term_registration = models.BooleanField(default=False)
    teaching_timetable = models.BooleanField(default=False)
    feedback = models.BooleanField(default=False)
    assessments_results = models.BooleanField(default=False)
    attendance_lesson_plan = models.BooleanField(default=False)
    class Meta:
        db_table='platform_institution_module'


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    institution = models.ForeignKey('organization.Institution', on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table='platform_institution_membership'
        constraints=[models.UniqueConstraint(fields=['user','institution'],name='uq_platform_membership')]


class ScopeGrant(models.Model):
    class Role(models.TextChoices):
        INSTITUTION_ADMIN='INSTITUTION_ADMIN'; CAMPUS_ADMIN='CAMPUS_ADMIN'; DEPARTMENT_ADMIN='DEPARTMENT_ADMIN'; TEACHER='TEACHER'; STUDENT='STUDENT'
    membership = models.ForeignKey(Membership,on_delete=models.PROTECT,related_name='grants')
    role = models.CharField(max_length=20,choices=Role.choices)
    campus = models.ForeignKey('organization.Campus',on_delete=models.PROTECT,null=True,blank=True)
    department = models.ForeignKey('organization.Department',on_delete=models.PROTECT,null=True,blank=True)
    is_active = models.BooleanField(default=True)
    # Optional per-resource allowlists restrict, never expand, the assigned scope.
    record_limits = models.JSONField(default=dict,blank=True)
    class Meta:
        db_table='platform_organization_scope'
        constraints=[models.CheckConstraint(condition=
            Q(role='INSTITUTION_ADMIN',campus__isnull=True,department__isnull=True)|
            Q(role='CAMPUS_ADMIN',campus__isnull=False,department__isnull=True)|
            Q(role='DEPARTMENT_ADMIN',campus__isnull=False,department__isnull=False)|
            (Q(role__in=['TEACHER','STUDENT'])&(Q(department__isnull=True)|Q(campus__isnull=False))),name='chk_organization_role_scope')]

    def clean(self):
        if self.campus_id and self.campus.institution_id != self.membership.institution_id:
            raise ValidationError({'campus':'Campus must belong to the membership institution.'})
        if self.department_id and self.department.campus_id != self.campus_id:
            raise ValidationError({'department':'Department must belong to the selected campus.'})
        from apps.organization.catalogue import RESOURCES
        allowed={'feedback-cycles','assessment-offerings','assessment-events','attendance-sections','attendance-sessions'} | {'registration-'+name for name in ('offerings','sections','batches','terms','courses','mappings','registrations','rosters','policies','audit')} | {r.path for r in RESOURCES} | {'time-slots','courses','schemes','curriculum-courses','prerequisites','students','employees','agencies','student-addresses','guardians','residences','previous-education','entrance-exams','employee-addresses','assignments','competencies'}
        if not isinstance(self.record_limits,dict) or any(key not in allowed or not isinstance(ids,list) or len(ids)>500 or any(type(pk) is not int or pk<1 for pk in ids) for key,ids in self.record_limits.items()):
            raise ValidationError({'record_limits':'Use resource names mapped to lists of at most 500 positive integer IDs.'})


