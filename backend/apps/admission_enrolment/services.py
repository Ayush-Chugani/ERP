import hashlib
import json
from functools import wraps
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError, ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError, PermissionDenied, NotFound
from . import models as m
from .policies import allowed, scoped, institution_create


class Conflict(APIException):
    status_code = 409
    default_code = 'admission_conflict'
    default_detail = 'The record changed or the requested operation conflicts with current data.'


def command(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='organization', model='university')
                kwargs['actor'] = get_user_model().objects.get(pk=kwargs['actor'].pk)
                return fn(*args, **kwargs)
        except IntegrityError as exc:
            if exc.args and exc.args[0] in (1062,1451,1452,3819,4025):
                raise Conflict() from None
            raise
        except ModelValidationError as exc:
            raise ValidationError(getattr(exc, 'message_dict', exc.messages)) from None
        except ObjectDoesNotExist:
            raise ValidationError('A referenced record is unavailable.') from None
    return run


def get_locked(model, actor, pk, action, version=None):
    if not allowed(actor, action, model):
        raise PermissionDenied()
    obj = scoped(model, actor, action).select_for_update().filter(pk=pk).first()
    if obj is None:
        raise NotFound()
    if version is not None and str(obj.version) != str(version):
        raise Conflict('Stale version. Reload before retrying.')
    return obj


def reason_required(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValidationError({'reason': 'Supply a nonblank reason of at most 500 characters.'})


def event(obj, actor, action, reason, before=None):
    institution = obj.institution_id if isinstance(obj,m.AdmissionApplicant) else obj.programme.department.campus.institution_id
    state = getattr(obj,'application_status',getattr(obj,'enrolment_status',None))
    audit = m.AdmissionAudit.objects.create(actor=actor, institution_id=institution,
        action=action, resource=obj._meta.model_name, record_id=obj.pk, reason=reason,
        changes={'old_status':before, 'new_status':state, 'version':obj.version})
    m.AdmissionOutbox.objects.create(audit=audit, event_type='admission.'+action+'.v1',
        payload={'record_id':str(obj.pk),'institution_id':str(institution)})


APPLICANT_FIELDS = set('institution_id first_name middle_name last_name display_name date_of_birth gender_id primary_email primary_phone nationality_country_id social_category_id caste_id sub_caste_id'.split())
APPLICATION_FIELDS = set('admission_applicant_id programme_id specialization_id academic_year_id admission_category_id application_date remarks'.split())


@command
def save_record(*, actor, model, values, pk=None, version=None):
    if model not in (m.AdmissionApplicant,m.AdmissionApplication):
        raise ValidationError('Unsupported resource.')
    action = 'change' if pk else 'add'
    if not allowed(actor,action,model):
        raise PermissionDenied()
    if pk and version is None:
        raise ValidationError('Version is required.')
    obj = get_locked(model,actor,pk,action,version) if pk else model(created_by=actor)
    fields = APPLICANT_FIELDS if model is m.AdmissionApplicant else APPLICATION_FIELDS
    if set(values)-fields:
        raise ValidationError('Unsupported or protected fields.')
    if pk and isinstance(obj,m.AdmissionApplication) and obj.application_status != 'DRAFT':
        raise Conflict('Only draft applications can be edited.')
    if pk and isinstance(obj,m.AdmissionApplicant):
        if 'institution_id' in values and values['institution_id'] != obj.institution_id:
            raise ValidationError('Institution cannot be changed.')
        if m.AdmissionApplication.objects.filter(admission_applicant=obj).exclude(application_status='DRAFT').exists():
            raise Conflict('Applicant is referenced by a submitted application.')
    old = {f.attname:getattr(obj,f.attname) for f in obj._meta.fields}
    for name,value in values.items():
        if isinstance(value,str):
            value = value.strip()
            if name == 'primary_email':
                value = value.lower()
            if not value and obj._meta.get_field(name).null:
                value = None
        setattr(obj,name,value)
    if isinstance(obj,m.AdmissionApplicant):
        if not pk:
            institution_create(actor,obj.institution_id)
        if set(values) & {'date_of_birth','primary_email','primary_phone','social_category_id','caste_id','sub_caste_id'} and not allowed(actor,'sensitive'):
            raise PermissionDenied('Sensitive demographic permission required.')
    else:
        if not scoped(m.AdmissionApplicant,actor).filter(pk=obj.admission_applicant_id).exists():
            raise NotFound('Applicant unavailable.')
        if not pk:
            obj.application_number = 'APP-' + uuid4().hex[:26].upper()
        if obj.academic_year.status not in ('PLANNED','ACTIVE'):
            raise ValidationError('Applications require a planned or active year.')
    for f in obj._meta.fields:
        if f.is_relation and f.name not in ('created_by','updated_by') and getattr(obj,f.attname) is not None and old.get(f.attname) != getattr(obj,f.attname):
            parent = getattr(obj,f.name)
            if hasattr(parent,'is_active') and not parent.is_active:
                raise ValidationError({f.name:'Select an active parent.'})
    obj.updated_by = actor
    if pk:
        obj.version += 1
    obj.full_clean()
    obj.save()
    if not scoped(model,actor,action).filter(pk=obj.pk).exists():
        raise PermissionDenied()
    event(obj,actor,'record.updated' if pk else 'record.created','Record saved')
    return obj


TRANSITIONS = {
    'DRAFT': {'SUBMITTED','CANCELLED'}, 'SUBMITTED': {'UNDER_REVIEW','CANCELLED'},
    'UNDER_REVIEW': {'ELIGIBLE','INELIGIBLE','CANCELLED'}, 'ELIGIBLE': {'SELECTED','WAITLISTED','REJECTED','CANCELLED'},
    'WAITLISTED': {'SELECTED','REJECTED','CANCELLED'}, 'SELECTED': {'CANCELLED'},
    'INELIGIBLE': {'UNDER_REVIEW'}, 'REJECTED': {'UNDER_REVIEW'}, 'CANCELLED': {'UNDER_REVIEW'},
}


@command
def transition_application(*, actor, pk, version, target, reason):
    reason_required(reason)
    if version is None:
        raise ValidationError('Version is required.')
    permission = 'reopen' if target == 'UNDER_REVIEW' else 'select' if target in ('SELECTED','WAITLISTED','REJECTED') else 'review'
    obj = get_locked(m.AdmissionApplication,actor,pk,permission,version)
    if target not in TRANSITIONS.get(obj.application_status,set()):
        raise Conflict('Invalid application transition.')
    old = obj.application_status
    obj.application_status = target
    if target in ('ELIGIBLE','INELIGIBLE'):
        obj.eligibility_status = target
    elif target == 'UNDER_REVIEW':
        obj.eligibility_status = 'PENDING'
        obj.reviewer = actor
    obj.version += 1
    obj.updated_by = actor
    obj.full_clean(); obj.save()
    event(obj,actor,'application.transition',reason,old)
    return obj


@command
def record_clearance(*, actor, pk, version, reference):
    if version is None:
        raise ValidationError('Version is required.')
    obj = get_locked(m.AdmissionApplication,actor,pk,'clearance',version)
    if obj.application_status != 'SELECTED':
        raise Conflict('Clearance is recorded for selected applications.')
    if not isinstance(reference,str) or not reference.strip() or len(reference)>150:
        raise ValidationError({'reference':'Supply a reference of at most 150 characters.'})
    record = m.FeeClearance.objects.create(application=obj,actor=actor,reference=reference.strip(),application_version=obj.version)
    event(obj,actor,'fee.attested','Manual clearance recorded')
    return record


def history(obj,actor,old,reason,effective_date):
    last = m.EnrolmentStatusHistory.objects.filter(enrolment=obj).order_by('-sequence_number').first()
    if effective_date < obj.admission_date or effective_date > timezone.localdate() or last and effective_date < last.effective_date:
        raise ValidationError('Effective date must follow prior history and cannot be in the future.')
    row = m.EnrolmentStatusHistory(enrolment=obj,actor=actor,old_status=old,new_status=obj.enrolment_status,
        sequence_number=(last.sequence_number+1 if last else 1),effective_date=effective_date,reason=reason,source='command',request_id=str(uuid4()))
    row.full_clean(); row.save()


@command
def admit_application(*, actor, application_id, version, payload, idempotency_key):
    if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=100:
        raise ValidationError('Supply an idempotency key of at most 100 characters.')
    obj = get_locked(m.AdmissionApplication,actor,application_id,'admit')
    digest = hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    receipt = m.CommandReceipt.objects.filter(actor=actor,application=obj,key=idempotency_key).first()
    if receipt:
        if receipt.digest != digest:
            raise Conflict('Idempotency key was used with different data.')
        return receipt.enrolment
    if str(obj.version)!=str(version):
        raise Conflict('Stale version.')
    if obj.application_status!='SELECTED' or obj.eligibility_status!='ELIGIBLE':
        raise Conflict('Application must be selected and eligible.')
    if not m.FeeClearance.objects.filter(application=obj,application_version=obj.version).exists():
        raise Conflict('Authorized manual fee clearance is required.')
    required = {'student_id','curriculum_scheme_id','admission_semester_id','admission_date'}
    if set(payload)-required-{'expected_completion_date'} or not required <= set(payload):
        raise ValidationError('Supply student, scheme, semester and admission date.')
    from apps.people_master.public import admission_student
    student = admission_student(actor=actor, institution_id=obj.admission_applicant.institution_id, student_id=payload['student_id'])
    applicant = m.AdmissionApplicant.objects.select_for_update().get(pk=obj.admission_applicant_id)
    if applicant.canonical_student_id and applicant.canonical_student_id != student.pk:
        raise Conflict('Applicant is already linked to a different student.')
    if obj.academic_year.status!='ACTIVE' or not obj.programme.is_active:
        raise Conflict('Admission year and programme must be active.')
    enrolment = m.StudentProgrammeEnrolment(application=obj,student=student,programme=obj.programme,
        specialization=obj.specialization,admission_academic_year=obj.academic_year,admission_category=obj.admission_category,
        created_by=actor,updated_by=actor,**{k:v for k,v in payload.items() if k!='student_id'})
    scheme = enrolment.curriculum_scheme
    from datetime import date
    if isinstance(enrolment.admission_date,str):
        try:
            enrolment.admission_date = date.fromisoformat(enrolment.admission_date)
        except ValueError:
            raise ValidationError('Invalid admission date.') from None
    if scheme.status!='ACTIVE' or not scheme.effective_from<=enrolment.admission_date or scheme.effective_to and scheme.effective_to<enrolment.admission_date:
        raise Conflict('Scheme must be active and valid on the admission date.')
    obj.application_status='ADMITTED'; obj.admitted_student=student; obj.version+=1; obj.updated_by=actor
    obj.full_clean(); obj.save()
    enrolment.full_clean(); enrolment.save()
    applicant.canonical_student=student; applicant.version+=1; applicant.updated_by=actor; applicant.save()
    history(enrolment,actor,None,'Admission approved',enrolment.admission_date)
    m.CommandReceipt.objects.create(actor=actor,application=obj,key=idempotency_key,digest=digest,enrolment=enrolment)
    event(obj,actor,'application.transition','Admission approved','SELECTED')
    event(enrolment,actor,'enrolment.created','Admission approved')
    return enrolment


@command
def transition_enrolment(*, actor, pk, version, target, reason, effective_date):
    reason_required(reason)
    if version is None:
        raise ValidationError('Version is required.')
    obj = get_locked(m.StudentProgrammeEnrolment,actor,pk,'lifecycle',version)
    valid = {'ACTIVE':{'ON_BREAK','WITHDRAWN','COMPLETED','TERMINATED'},'ON_BREAK':{'ACTIVE','WITHDRAWN','TERMINATED'}}
    if target not in valid.get(obj.enrolment_status,set()):
        raise Conflict('Invalid enrolment transition.')
    old=obj.enrolment_status; obj.enrolment_status=target; obj.version+=1; obj.updated_by=actor
    history(obj,actor,old,reason,effective_date)
    obj.full_clean(); obj.save(); event(obj,actor,'enrolment.transition',reason,old)
    return obj


@command
def finalize_exit_enrolment(*, actor, pk, version, target, reason, effective_date):
    """M13 integration after clearance; deliberately not exposed by the generic M6 API."""
    reason_required(reason)
    if version is None:
        raise ValidationError('Version is required.')
    obj = get_locked(m.StudentProgrammeEnrolment, actor, pk, 'lifecycle', version)
    valid = {'ACTIVE': {'COMPLETED', 'TRANSFERRED', 'WITHDRAWN', 'TERMINATED'},
             'ON_BREAK': {'TRANSFERRED', 'WITHDRAWN', 'TERMINATED'}}
    if target not in valid.get(obj.enrolment_status, set()):
        raise Conflict('Invalid final exit enrolment transition.')
    old = obj.enrolment_status
    obj.enrolment_status = target
    obj.version += 1
    obj.updated_by = actor
    history(obj, actor, old, reason, effective_date)
    obj.full_clean()
    obj.save()
    event(obj, actor, 'enrolment.exit_finalized', reason, old)
    return obj
