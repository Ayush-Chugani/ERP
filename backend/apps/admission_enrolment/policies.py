from django.conf import settings
from django.db.models import Q, F
from rest_framework.exceptions import PermissionDenied
from apps.tenancy.models import ScopeGrant
from . import models as m


def allowed(actor, action, model=m.AdmissionApplication):
    code = f'{action}_{model._meta.model_name}' if action in ('view','add','change') else f'{action}_admission'
    if action == 'clearance':
        code = 'record_fee_clearance'
    return bool(getattr(settings, 'ADMISSION_ENROLMENT_ENABLED', False) and actor.is_authenticated and actor.is_active and (actor.is_superuser or actor.has_perm('admission_enrolment.' + code)))


def grants(actor):
    return ScopeGrant.objects.filter(
        membership__user=actor, membership__is_active=True, is_active=True,
        membership__institution__is_active=True,
        membership__institution__university__is_active=True,
        membership__institution__institutionmodule__admission_enrolment=True,
        role__in=['INSTITUTION_ADMIN','CAMPUS_ADMIN','DEPARTMENT_ADMIN'],
    ).filter(Q(campus__isnull=True) | Q(campus__institution=F('membership__institution'))).filter(
        Q(department__isnull=True) | Q(department__campus=F('campus'))
    ).select_related('membership')


def scoped(model, actor, action='view'):
    qs = model.objects.all()
    if not allowed(actor, action, model):
        return qs.none()
    if actor.is_superuser:
        return qs
    condition = Q(pk__in=[])
    for grant in grants(actor):
        if model is m.AdmissionApplicant:
            part = Q(institution_id=grant.membership.institution_id)
            if grant.campus_id or grant.department_id:
                apps = scoped(m.AdmissionApplication, actor, 'view')
                part &= Q(pk__in=apps.values('admission_applicant_id'))
            path = 'applicants'
        else:
            prefix = 'enrolment__' if model is m.EnrolmentStatusHistory else ''
            part = Q(**{prefix+'programme__department__campus__institution_id': grant.membership.institution_id})
            if grant.campus_id:
                part &= Q(**{prefix+'programme__department__campus_id': grant.campus_id})
            if grant.department_id:
                part &= Q(**{prefix+'programme__department_id': grant.department_id})
            path = 'applications' if model is m.AdmissionApplication else 'enrolments'
        if not isinstance(grant.record_limits, dict):
            continue
        if path in grant.record_limits:
            part &= Q(pk__in=grant.record_limits[path])
        condition |= part
    return qs.filter(condition).distinct()


def institution_create(actor, institution_id):
    if actor.is_superuser:
        return
    if not grants(actor).filter(role='INSTITUTION_ADMIN', membership__institution_id=institution_id).exists():
        raise PermissionDenied('Institution admissions authority is required to create an applicant.')
