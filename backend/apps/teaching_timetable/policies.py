from django.conf import settings
from django.db.models import F, Q
from rest_framework.exceptions import NotFound, PermissionDenied
from apps.organization.models import Programme
from apps.tenancy.models import ScopeGrant


def enabled(actor, action):
    return bool(getattr(settings, 'TEACHING_TIMETABLE_ENABLED', False)
                and actor.is_authenticated and actor.is_active
                and (actor.is_superuser or actor.has_perm('teaching_timetable.' + action)))


def grants(actor):
    return ScopeGrant.objects.filter(
        membership__user=actor, membership__is_active=True, is_active=True,
        membership__institution__institutionmodule__teaching_timetable=True,
        membership__institution__is_active=True,
        membership__institution__university__is_active=True,
    ).filter(Q(campus__isnull=True) | Q(campus__institution=F('membership__institution'))).filter(
        Q(department__isnull=True) | Q(department__campus=F('campus')),
    ).select_related('membership')


def programmes(actor, action='manage_timetable'):
    qs = Programme.objects.filter(is_active=True, department__is_active=True,
        department__campus__is_active=True, department__campus__institution__is_active=True,
        department__campus__institution__university__is_active=True)
    if not enabled(actor, action):
        return qs.none()
    if actor.is_superuser:
        return qs
    condition = Q(pk__in=[])
    for grant in grants(actor).filter(role__in=['INSTITUTION_ADMIN', 'CAMPUS_ADMIN', 'DEPARTMENT_ADMIN']):
        part = Q(department__campus__institution_id=grant.membership.institution_id)
        if grant.campus_id:
            part &= Q(department__campus_id=grant.campus_id)
        if grant.department_id:
            part &= Q(department_id=grant.department_id)
        limits = grant.record_limits
        if not isinstance(limits, dict):
            continue
        if 'programmes' in limits:
            ids = limits['programmes']
            if not isinstance(ids, list) or any(type(pk) is not int or pk < 1 for pk in ids):
                continue
            part &= Q(pk__in=ids)
        condition |= part
    return qs.filter(condition)


def require_programme(actor, programme_id, action='manage_timetable'):
    if not programmes(actor, action).filter(pk=programme_id).exists():
        raise NotFound('Scheduling resource unavailable.')


def require_institution(actor, institution_id, action='configure_timetable'):
    if not enabled(actor, action):
        raise PermissionDenied('Scheduling authority unavailable.')
    if not actor.is_superuser and not grants(actor).filter(
        role='INSTITUTION_ADMIN', membership__institution_id=institution_id,
    ).exists():
        raise NotFound('Scheduling resource unavailable.')


def require_resources(actor, section, references):
    """One matching grant must cover the programme and every referenced resource."""
    if actor.is_superuser:
        return
    programme = section.programme_term_offering.programme
    for grant in grants(actor).filter(membership__institution_id=programme.department.campus.institution_id,
        role__in=['INSTITUTION_ADMIN', 'CAMPUS_ADMIN', 'DEPARTMENT_ADMIN']):
        if grant.campus_id and grant.campus_id != programme.department.campus_id:
            continue
        if grant.department_id and grant.department_id != programme.department_id:
            continue
        limits = grant.record_limits
        if not isinstance(limits, dict):
            continue
        requested = {'programmes': programme.pk, **references}
        if all(pk is None or resource not in limits or
               (isinstance(limits[resource], list) and pk in limits[resource])
               for resource, pk in requested.items()):
            return
    raise NotFound('Scheduling resource unavailable.')
