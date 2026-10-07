import re
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django.core.validators import MinValueValidator
from apps.core.fields import UnsignedAutoField, ReferenceTextField
from .fields import UnsignedTinyIntegerField

COLLATION = 'utf8mb4_0900_ai_ci'


def text(length, *, optional=False, code=False, unique=False):
    return ReferenceTextField(max_length=length, null=optional, blank=optional,
        kind='code' if code else 'description', unique=unique, db_collation=COLLATION)


def parent(model, column, optional=False):
    return models.ForeignKey(model, on_delete=models.PROTECT, db_column=column, null=optional, blank=optional)


class OrganizationRecord(models.Model):
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if isinstance(value, str):
                import unicodedata
                value = unicodedata.normalize('NFC', value).strip()
                if isinstance(field, ReferenceTextField):
                    value = field.to_python(value)
                setattr(self, field.attname, value if value else (None if field.null else ''))
        errors = {}
        phone = getattr(self, 'phone', None)
        if phone and (not re.fullmatch(r'\+?[0-9 ()-]+', phone) or not any(c.isdigit() for c in phone)):
            errors['phone'] = 'Use digits with an optional leading +, spaces, parentheses or hyphens.'
        postal = getattr(self, 'postal_code', None)
        if postal and not all(c.isalnum() or c in ' -' for c in postal):
            errors['postal_code'] = 'Use letters, digits, spaces or hyphens.'
        if getattr(self, 'website_url', None) and not self.website_url.startswith(('http://', 'https://')):
            errors['website_url'] = 'Use an HTTP or HTTPS URL.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        for field in self._meta.fields:
            if field.name.endswith('_name'):
                return getattr(self, field.name) or str(self.pk)
        return str(self.pk)


class University(OrganizationRecord):
    class Type(models.TextChoices):
        CENTRAL='CENTRAL'; STATE='STATE'; PRIVATE='PRIVATE'; DEEMED='DEEMED'; OTHER='OTHER'
    university_id = UnsignedAutoField(bits=16, primary_key=True)
    university_code = text(30, code=True, unique=True)
    university_name = text(200)
    legal_name = text(250, optional=True)
    university_type = models.CharField(max_length=10, choices=Type.choices, default=Type.OTHER)
    website_url = models.URLField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    phone = text(25, optional=True)
    address_line_1 = text(200, optional=True)
    address_line_2 = text(200, optional=True)
    city = text(100, optional=True)
    state = parent('common_reference.State', 'state_id', True)
    postal_code = text(12, optional=True)

    class Meta:
        db_table='university'
        ordering=['university_code','university_id']
        constraints=[models.CheckConstraint(condition=Q(university_type__in=['CENTRAL','STATE','PRIVATE','DEEMED','OTHER']), name='chk_university_type')]


class Institution(OrganizationRecord):
    institution_id = UnsignedAutoField(bits=16, primary_key=True)
    university = parent(University, 'university_id')
    institution_code = text(20, code=True, unique=True)
    institution_name = text(200)
    legal_name = text(250, optional=True)
    website_url = models.URLField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    phone = text(25, optional=True)

    class Meta:
        db_table='institution'
        ordering=['institution_code','institution_id']


class Campus(OrganizationRecord):
    campus_id = UnsignedAutoField(bits=16, primary_key=True)
    institution = parent(Institution, 'institution_id')
    campus_code = text(20, code=True)
    campus_name = text(150)
    address_line_1 = text(200, optional=True)
    address_line_2 = text(200, optional=True)
    city = text(100, optional=True)
    state = parent('common_reference.State', 'state_id', True)
    postal_code = text(12, optional=True)
    phone = text(25, optional=True)
    email = models.EmailField(max_length=254, null=True, blank=True)

    class Meta:
        db_table='campus'
        ordering=['campus_code','campus_id']
        constraints=[models.UniqueConstraint(fields=['institution','campus_code'], name='uq_campus_code')]


class Department(OrganizationRecord):
    department_id = UnsignedAutoField(bits=16, primary_key=True)
    campus = parent(Campus, 'campus_id')
    department_code = text(20, code=True)
    department_name = text(150)
    department_type = text(30, optional=True)

    class Meta:
        db_table='department'
        ordering=['department_code','department_id']
        constraints=[models.UniqueConstraint(fields=['campus','department_code'], name='uq_department_code'), models.UniqueConstraint(fields=['department_id','campus'], name='uq_department_id_campus')]


class Programme(OrganizationRecord):
    class Level(models.TextChoices):
        UG='UG'; PG='PG'; DIPLOMA='DIPLOMA'; CERTIFICATE='CERTIFICATE'; DOCTORAL='DOCTORAL'; OTHER='OTHER'
    programme_id = UnsignedAutoField(bits=16, primary_key=True)
    department = parent(Department, 'department_id')
    programme_code = text(30, code=True, unique=True)
    programme_name = text(150)
    award_name = text(150, optional=True)
    programme_level = models.CharField(max_length=12, choices=Level.choices)
    duration_semesters = UnsignedTinyIntegerField(validators=[MinValueValidator(1)])
    maximum_duration_semesters = UnsignedTinyIntegerField(null=True, blank=True)

    class Meta:
        db_table='programme'
        ordering=['programme_code','programme_id']
        constraints=[models.CheckConstraint(condition=Q(duration_semesters__gt=0)&(Q(maximum_duration_semesters__isnull=True)|Q(maximum_duration_semesters__gte=F('duration_semesters'))),name='chk_programme_duration'), models.CheckConstraint(condition=Q(programme_level__in=['UG','PG','DIPLOMA','CERTIFICATE','DOCTORAL','OTHER']),name='chk_programme_level')]


class ProgrammeSpecialization(OrganizationRecord):
    specialization_id = UnsignedAutoField(bits=16, primary_key=True)
    programme = parent(Programme, 'programme_id')
    specialization_code = text(30, code=True)
    specialization_name = text(150)

    class Meta:
        db_table='programme_specialization'
        ordering=['specialization_code','specialization_id']
        constraints=[models.UniqueConstraint(fields=['programme','specialization_code'],name='uq_specialization_code'),models.UniqueConstraint(fields=['specialization_id','programme'],name='uq_specialization_programme')]


class Building(OrganizationRecord):
    building_id = UnsignedAutoField(bits=16, primary_key=True)
    campus = parent(Campus, 'campus_id')
    building_code = text(20, code=True)
    building_name = text(100)

    class Meta:
        db_table='building'
        ordering=['building_code','building_id']
        constraints=[models.UniqueConstraint(fields=['campus','building_code'],name='uq_building_code')]


class Room(OrganizationRecord):
    class Type(models.TextChoices):
        CLASSROOM='CLASSROOM'; LAB='LAB'; SEMINAR_HALL='SEMINAR_HALL'; AUDITORIUM='AUDITORIUM'; OFFICE='OFFICE'; OTHER='OTHER'
    room_id = UnsignedAutoField(bits=32, primary_key=True)
    building = parent(Building, 'building_id')
    room_code = text(20, code=True)
    room_name = text(100, optional=True)
    room_type = models.CharField(max_length=15, choices=Type.choices)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])

    class Meta:
        db_table='room'
        ordering=['room_code','room_id']
        constraints=[models.UniqueConstraint(fields=['building','room_code'],name='uq_room_code'),models.CheckConstraint(condition=Q(capacity__isnull=True)|Q(capacity__gt=0),name='chk_room_capacity'),models.CheckConstraint(condition=Q(room_type__in=['CLASSROOM','LAB','SEMINAR_HALL','AUDITORIUM','OFFICE','OTHER']),name='chk_room_type')]

class OrganizationAudit(models.Model):
    """Platform support history, not part of the legacy organization schema."""
    from apps.core.models import AppendOnlyQuerySet
    from django.conf import settings
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    resource = models.CharField(max_length=40)
    record_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=12)
    timestamp = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()
    class Meta:
        db_table='platform_organization_audit'
        default_permissions=('view',)
        ordering=['-timestamp','-pk']
    def save(self,*args,**kwargs):
        if not self._state.adding: raise ValidationError('Audit events cannot be updated.')
        kwargs['force_insert']=True
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError('Audit events cannot be deleted.')
