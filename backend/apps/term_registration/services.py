from functools import wraps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError, OperationalError, models
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError, PermissionDenied
from . import models as m
from .policies import require_programme, SEAT_STATUSES


class RegistrationConflict(APIException):
    status_code=409
    default_code='registration_conflict'
    default_detail='Registration conflicts with the current record state.'


def command(fn):
    @wraps(fn)
    def run(*args,**kwargs):
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='organization',model='university')
                kwargs['actor']=get_user_model().objects.get(pk=kwargs['actor'].pk)
                return fn(*args,**kwargs)
        except IntegrityError as exc:
            if exc.args and exc.args[0] in (1062,1451,1452,3819,4025):
                raise RegistrationConflict('Duplicate values or invalid ownership constraints.') from None
            raise
        except ModelValidationError as exc:
            raise ValidationError(getattr(exc,'message_dict',exc.messages)) from None
        except ObjectDoesNotExist:
            raise ValidationError('Referenced record unavailable.') from None
        except OperationalError as exc:
            if exc.args and exc.args[0] in (1205,1213):
                raise RegistrationConflict('Concurrent update; refresh and retry with the same key.') from None
            raise
    return run


def require_reason(reason):
    if not isinstance(reason,str) or not reason.strip() or len(reason)>500:
        raise ValidationError('Supply a nonblank reason of at most 500 characters.')


def audit(obj,actor,programme,action,reason,before=None):
    after=snapshot(obj)
    evidence=m.RegistrationAudit.objects.create(actor=actor,programme_id=programme,resource=obj._meta.model_name,record_id=obj.pk,action=action,reason=reason,before=before or {},after=after)
    category='roster' if isinstance(obj,m.CourseOfferingSectionStudent) else 'course' if isinstance(obj,m.StudentCourseRegistration) else 'term' if isinstance(obj,m.StudentTermRegistration) else 'offering'
    m.RegistrationEvent.objects.create(audit=evidence,event_type=f'registration.{category}.changed.v1',payload={'audit_id':str(evidence.pk),'record_id':str(obj.pk),'resource':obj._meta.model_name,'programme_id':str(programme),'actor_id':str(actor.pk),'before':before or {},'after':after})


def snapshot(obj):
    return {f.attname: str(getattr(obj,f.attname)) if getattr(obj,f.attname) is not None else None
            for f in obj._meta.concrete_fields if not isinstance(f,models.GeneratedField) and f.name not in ('created_at','updated_at')}


def save_validated(obj):
    obj.full_clean(exclude=[f.name for f in obj._meta.fields if isinstance(f,models.GeneratedField)])
    obj.save()
    return obj


def matching_enrolment(enrolment,offering):
    if enrolment.enrolment_status!='ACTIVE':
        raise RegistrationConflict('Enrolment must be active.')
    if (enrolment.programme_id,enrolment.specialization_id,enrolment.curriculum_scheme_id)!=(offering.programme_id,offering.specialization_id,offering.curriculum_scheme_id):
        raise ValidationError('Enrolment programme, specialization and scheme must match.')
    if enrolment.student.institution_id!=offering.programme.department.campus.institution_id:
        raise ValidationError('Student institution does not match offering.')
    if enrolment.student.student_status != 'ACTIVE':
        raise RegistrationConflict('Student must be active.')


@command
def approve_progression(*,actor,enrolment_id,offering_id,offering_version,enrolment_version,reason):
    require_reason(reason)
    from .workflows import get
    offering=get(actor,'offerings',offering_id,'approve_progression')
    require_programme(actor,offering.programme_id,'approve_progression')
    from apps.admission_enrolment.models import StudentProgrammeEnrolment
    enrolment=StudentProgrammeEnrolment.objects.select_for_update().get(pk=enrolment_id)
    matching_enrolment(enrolment,offering)
    from .selectors import require_references
    require_references(actor,offering.programme_id,{'students':enrolment.student_id})
    if str(offering.version)!=str(offering_version) or str(enrolment.version)!=str(enrolment_version):
        raise RegistrationConflict('Stale offering or enrolment version.')
    record=m.ProgressionApproval(enrolment=enrolment,offering=offering,enrolment_version=enrolment.version,offering_version=offering.version,actor=actor,reason=reason.strip())
    save_validated(record)
    audit(record,actor,offering.programme_id,'progression_approved',reason)
    return record


@command
def create_draft(*,actor,enrolment_id,offering_id,section_id=None,batch_id=None):
    from .workflows import get
    offering=get(actor,'offerings',offering_id)
    require_programme(actor,offering.programme_id)
    from apps.admission_enrolment.models import StudentProgrammeEnrolment
    enrolment=StudentProgrammeEnrolment.objects.select_for_update().get(pk=enrolment_id)
    matching_enrolment(enrolment,offering)
    from .selectors import require_references
    require_references(actor,offering.programme_id,{'students':enrolment.student_id})
    if offering.status not in ('PLANNED','REGISTRATION_OPEN'):
        raise RegistrationConflict('Offering does not accept draft registrations.')
    if section_id: get(actor,'sections',section_id)
    if batch_id: get(actor,'batches',batch_id)
    obj=m.StudentTermRegistration(enrolment=enrolment,programme_term_offering=offering,programme_id=offering.programme_id,class_section_id=section_id,class_batch_id=batch_id,registration_date=timezone.localdate(),created_by=actor,updated_by=actor)
    save_validated(obj)
    audit(obj,actor,offering.programme_id,'draft_created','Draft registration created')
    return obj


def check_capacity(obj):
    if not obj.class_section_id:
        raise ValidationError('Select a section before reserving a seat.')
    for field,model in [('class_section',m.ClassSection),('class_batch',m.ClassBatch)]:
        pk=getattr(obj,field+'_id')
        if not pk:
            continue
        parent=model.objects.select_for_update().get(pk=pk)
        if not parent.is_active:
            raise RegistrationConflict('Selected section or batch is inactive.')
        occupied=m.StudentTermRegistration.objects.filter(**{field+'_id':pk},registration_status__in=SEAT_STATUSES).exclude(pk=obj.pk).count()
        if parent.capacity is not None and occupied>=parent.capacity:
            raise RegistrationConflict('Selected section or batch is full.')


@command
def transition_term(*,actor,registration_id,expected_version,target,reason):
    require_reason(reason)
    from .workflows import get
    permission='approve_registration' if target=='APPROVED' else 'manage_registration'
    obj=get(actor,'terms',registration_id,permission)
    require_programme(actor,obj.programme_id,permission)
    if str(obj.version)!=str(expected_version):
        raise RegistrationConflict('Stale registration version.')
    transitions={'DRAFT':{'REGISTERED','CANCELLED'},'REGISTERED':{'APPROVED','CANCELLED'},'APPROVED':{'COMPLETED','CANCELLED'}}
    if target not in transitions.get(obj.registration_status,set()):
        raise RegistrationConflict('Invalid registration transition.')
    offering=m.ProgrammeTermOffering.objects.select_for_update().get(pk=obj.programme_term_offering_id)
    if target in SEAT_STATUSES:
        term=offering.academic_term
        today=timezone.localdate()
        if offering.status!='REGISTRATION_OPEN' or term.status!='REGISTRATION_OPEN' or not term.registration_start_date or not term.registration_end_date or not term.registration_start_date<=today<=term.registration_end_date:
            raise RegistrationConflict('Registration window is closed or not configured.')
        matching_enrolment(obj.enrolment,offering)
        if not m.ProgressionApproval.objects.filter(enrolment=obj.enrolment,offering=offering,enrolment_version=obj.enrolment.version,offering_version=offering.version).exists():
            raise RegistrationConflict('Current registrar progression approval is required.')
        check_capacity(obj)
        if m.StudentTermRegistration.objects.filter(enrolment=obj.enrolment,programme_term_offering__academic_term=offering.academic_term,registration_status__in=SEAT_STATUSES).exclude(pk=obj.pk).exists():
            raise RegistrationConflict('Student already reserves a seat in another offering of this academic term.')
    if target == 'APPROVED':
        from .workflows import credits
        policy=m.RegistrationPolicy.objects.filter(programme_id=obj.programme_id).first()
        if policy and not policy.minimum_credits <= credits(obj) <= policy.maximum_credits:
            raise RegistrationConflict('Registered credits are outside the configured limits.')
    if target in ('CANCELLED','COMPLETED') and m.StudentCourseRegistration.objects.filter(term_registration=obj,registration_status__in=SEAT_STATUSES).exists():
        raise RegistrationConflict('Resolve active course registrations first.')
    before={'registration_status':obj.registration_status,'version':obj.version}
    obj.registration_status=target;obj.version+=1;obj.updated_by=actor
    if target=='REGISTERED' and not obj.roll_number:
        obj.roll_number='R-'+str(obj.pk)
    save_validated(obj)
    audit(obj,actor,obj.programme_id,'term_transition',reason,before)
    return obj
