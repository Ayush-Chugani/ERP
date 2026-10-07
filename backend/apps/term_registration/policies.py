from django.conf import settings
from django.db.models import Q, F
from rest_framework.exceptions import PermissionDenied
from apps.organization.models import Programme
from apps.tenancy.models import ScopeGrant

SEAT_STATUSES=('REGISTERED','APPROVED')


def permitted(actor,action):
    return bool(getattr(settings,'TERM_REGISTRATION_ENABLED',False) and actor.is_authenticated and actor.is_active and (actor.is_superuser or actor.has_perm('term_registration.'+action)))


def programmes(actor,action='manage_registration'):
    qs=Programme.objects.filter(is_active=True, department__is_active=True,
        department__campus__is_active=True, department__campus__institution__is_active=True,
        department__campus__institution__university__is_active=True)
    if not permitted(actor,action):
        return qs.none()
    if actor.is_superuser:
        return qs
    grants=ScopeGrant.objects.filter(membership__user=actor,membership__is_active=True,is_active=True,
        membership__institution__institutionmodule__term_registration=True,
        membership__institution__is_active=True,membership__institution__university__is_active=True,
        role__in=['INSTITUTION_ADMIN','CAMPUS_ADMIN','DEPARTMENT_ADMIN']).filter(
        Q(campus__isnull=True)|Q(campus__institution=F('membership__institution'))).filter(
        Q(department__isnull=True)|Q(department__campus=F('campus'))).select_related('membership')
    condition=Q(pk__in=[])
    for grant in grants:
        part=Q(department__campus__institution_id=grant.membership.institution_id)
        if grant.campus_id:
            part &= Q(department__campus_id=grant.campus_id)
        if grant.department_id:
            part &= Q(department_id=grant.department_id)
        if not isinstance(grant.record_limits,dict):
            continue
        if 'programmes' in grant.record_limits:
            if not isinstance(grant.record_limits['programmes'],list) or any(type(pk) is not int or pk<1 for pk in grant.record_limits['programmes']):
                continue
            part &= Q(pk__in=grant.record_limits['programmes'])
        condition |= part
    return qs.filter(condition)


def require_programme(actor,programme_id,action='manage_registration'):
    if not programmes(actor,action).filter(pk=programme_id).exists():
        raise PermissionDenied('Registration authority is unavailable for this programme.')
