"""Scope is applied before lookup, filtering, pagination, and export."""
from django.db.models import Q, F
from rest_framework.exceptions import NotFound
from .policies import programmes
from .workflows import RESOURCES


def covering_grants(actor, programme):
    from apps.tenancy.models import ScopeGrant
    for grant in ScopeGrant.objects.filter(membership__user=actor,membership__is_active=True,is_active=True,
            membership__institution_id=programme.department.campus.institution_id,
            membership__institution__institutionmodule__term_registration=True,
            role__in=['INSTITUTION_ADMIN','CAMPUS_ADMIN','DEPARTMENT_ADMIN']):
        if grant.campus_id and grant.campus_id != programme.department.campus_id: continue
        if grant.department_id and grant.department_id != programme.department_id: continue
        limits = grant.record_limits
        if not isinstance(limits,dict) or any(not isinstance(ids,list) or any(type(pk) is not int or pk<1 for pk in ids) for ids in limits.values()): continue
        if 'programmes' in limits and programme.pk not in limits['programmes']: continue
        yield limits


def require_references(actor, programme_id, references):
    from apps.organization.models import Programme
    if actor.is_superuser: return
    programme = Programme.objects.get(pk=programme_id)
    for limits in covering_grants(actor,programme):
        if all(pk is None or name not in limits or int(pk) in limits[name] for name,pk in references.items()):
            return
    raise NotFound('Registration resource unavailable.')


def scoped(actor, resource, action='manage_registration'):
    model,path = RESOURCES[resource]
    allowed = programmes(actor,action)
    qs = model.objects.filter(**{path+'__in':allowed})
    joins={
        'offerings':['programme','academic_term','semester'],
        'sections':['programme_term_offering__programme'],
        'batches':['class_section__programme_term_offering__programme'],
        'terms':['enrolment__student','programme_term_offering__programme'],
        'courses':['course','programme_term_offering__programme'],
        'mappings':['course_offering__course','class_section','class_batch','programme_term_offering__programme'],
        'registrations':['course_offering__course','term_registration__enrolment__student','programme_term_offering__programme'],
        'rosters':['course_offering__course','course_registration__term_registration__enrolment__student','course_offering__programme_term_offering__programme'],
    }
    qs=qs.select_related(*joins.get(resource,[])) if resource in joins else qs
    if actor.is_superuser: return qs
    condition = Q(pk__in=[])
    for programme in allowed.select_related('department__campus'):
        for limits in covering_grants(actor,programme):
            part = Q(**{path:programme.pk})
            # M7 allowlists are namespaced to distinguish course offerings from catalog courses.
            key = 'registration-'+resource
            if key in limits: part &= Q(pk__in=limits[key])
            parents = {
                'sections': {'offerings':'programme_term_offering'},
                'batches': {'sections':'class_section','offerings':'class_section__programme_term_offering'},
                'terms': {'offerings':'programme_term_offering','sections':'class_section','batches':'class_batch'},
                'courses': {'offerings':'programme_term_offering'},
                'mappings': {'offerings':'programme_term_offering','courses':'course_offering','sections':'class_section','batches':'class_batch'},
                'registrations': {'terms':'term_registration','offerings':'programme_term_offering','courses':'course_offering'},
                'rosters': {'registrations':'course_registration','terms':'course_registration__term_registration','offerings':'course_offering__programme_term_offering','courses':'course_offering','mappings':'course_offering_section'},
            }.get(resource,{})
            for owner, relation in parents.items():
                if 'registration-'+owner in limits:
                    part &= Q(**{relation+'__in':limits['registration-'+owner]}) | Q(**{relation+'__isnull':True})
            if resource == 'audit' and any(k != 'programmes' for k in limits):
                # Evidence can contain related IDs; narrow grants use individual record histories.
                continue
            upstream={
                'offerings': {'schemes':'curriculum_scheme','specializations':'specialization'},
                'sections': {'rooms':'home_room','schemes':'programme_term_offering__curriculum_scheme'},
                'courses': {'courses':'course','curriculum-courses':'curriculum_course','schemes':'programme_term_offering__curriculum_scheme'},
                'mappings': {'courses':'course_offering__course','schemes':'programme_term_offering__curriculum_scheme'},
                'registrations': {'courses':'course_offering__course','schemes':'programme_term_offering__curriculum_scheme'},
                'rosters': {'courses':'course_offering__course','schemes':'course_offering__programme_term_offering__curriculum_scheme'},
                'terms': {'schemes':'programme_term_offering__curriculum_scheme'},
            }.get(resource,{})
            for key,relation in upstream.items():
                if key in limits: part &= Q(**{relation+'__in':limits[key]}) | Q(**{relation+'__isnull':True})
            if resource in ('terms','registrations','rosters'):
                student_path = {'terms':'enrolment__student','registrations':'term_registration__enrolment__student','rosters':'course_registration__term_registration__enrolment__student'}[resource]
                if 'students' in limits: part &= Q(**{student_path+'__in':limits['students']})
            condition |= part
    return qs.filter(condition)


def record(obj):
    from django.db import models
    result = {'id':str(obj.pk)}
    for f in obj._meta.concrete_fields:
        if isinstance(f,models.GeneratedField) or f.primary_key: continue
        value = getattr(obj,f.attname)
        if f.is_relation: value = str(value) if value is not None else None
        result[f.attname] = value
    from . import models as m
    if isinstance(obj,m.ProgrammeTermOffering):
        result['label']=f'{obj.programme.programme_name} / {obj.academic_term.term_code} / {obj.semester.semester_name}'
    elif isinstance(obj,m.CourseOffering):
        result['label']=f'{obj.offering_code} / {obj.course.course_code}'
    elif isinstance(obj,m.CourseOfferingSection):
        result['label']=f'{obj.course_offering.course.course_code} / {obj.class_section.section_code} / {obj.session_type}'
    elif isinstance(obj,(m.StudentTermRegistration,m.StudentCourseRegistration,m.CourseOfferingSectionStudent)):
        term=obj if isinstance(obj,m.StudentTermRegistration) else obj.term_registration if isinstance(obj,m.StudentCourseRegistration) else obj.course_registration.term_registration
        result['student_number']=term.enrolment.student.student_number
        result['roll_number']=term.roll_number
        result['label']=term.enrolment.student.student_number + (' / '+obj.course_offering.course.course_code if hasattr(obj,'course_offering') else '')
    return result


def personal(actor):
    from django.conf import settings
    from apps.people_master.models import AccountLink
    from apps.tenancy.models import Membership
    from . import models as m
    if not getattr(settings,'TERM_REGISTRATION_ENABLED',False) or not actor.is_authenticated or not actor.is_active:
        raise NotFound()
    link = AccountLink.objects.filter(user=actor,student__isnull=False,student__student_status='ACTIVE').first()
    if not link or not Membership.objects.filter(user=actor,institution=link.student.institution,is_active=True,
            institution__institutionmodule__term_registration=True,institution__is_active=True,institution__university__is_active=True).exists():
        raise NotFound('Verified student account and active membership required.')
    return m.StudentTermRegistration.objects.filter(enrolment__student=link.student).select_related('programme_term_offering')


def as_of_roster(qs, day):
    # Closed episodes remain members on dates before their exclusive end.
    return qs.filter(effective_from__lte=day).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=day))


def records_with_capacity(resource, rows):
    from django.db.models import Count
    from . import models as m
    result=[record(obj) for obj in rows]
    if resource not in ('sections','batches','courses'): return result
    relation={'sections':'class_section_id','batches':'class_batch_id','courses':'course_offering_id'}[resource]
    model=m.StudentCourseRegistration if resource=='courses' else m.StudentTermRegistration
    counts=dict(model.objects.filter(**{relation+'__in':[obj.pk for obj in rows]},registration_status__in=['REGISTERED','APPROVED']).values(relation).annotate(total=Count('pk')).values_list(relation,'total'))
    for obj,row in zip(rows,result):
        capacity=getattr(obj,'registration_capacity',None) if resource=='courses' else obj.capacity
        row['occupied']=counts.get(obj.pk,0)
        row['remaining']=None if capacity is None else capacity-row['occupied']
    return result


def personal_offerings(actor):
    from django.utils import timezone
    from . import models as m
    from apps.people_master.models import AccountLink
    from apps.admission_enrolment.models import StudentProgrammeEnrolment
    personal(actor)  # Verify account link, institution, module and active membership.
    student_id=AccountLink.objects.get(user=actor,student__isnull=False).student_id
    today=timezone.localdate()
    matches=Q(pk__in=[])
    for enrolment in StudentProgrammeEnrolment.objects.filter(student_id=student_id,enrolment_status='ACTIVE'):
        approved=m.ProgressionApproval.objects.filter(enrolment=enrolment,enrolment_version=enrolment.version,offering_version=F('offering__version')).values('offering_id')
        matches |= Q(pk__in=approved,programme_id=enrolment.programme_id,specialization_id=enrolment.specialization_id,curriculum_scheme_id=enrolment.curriculum_scheme_id)
    return m.ProgrammeTermOffering.objects.filter(matches,status='REGISTRATION_OPEN',academic_term__status='REGISTRATION_OPEN',academic_term__registration_start_date__lte=today,academic_term__registration_end_date__gte=today,programme__is_active=True).select_related('programme','academic_term','semester')
