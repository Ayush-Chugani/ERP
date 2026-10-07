from django.conf import settings
from django.db.models import Q, F
from apps.tenancy.models import ScopeGrant
from apps.organization.models import Campus


def enabled(actor):
    return bool(getattr(settings, 'ACADEMIC_CALENDAR_ENABLED', True) and actor and actor.is_authenticated and actor.is_active)


def grants(actor, institution_id=None):
    rows = ScopeGrant.objects.filter(membership__user=actor, membership__is_active=True,
        membership__institution__institutionmodule__academic_calendar=True, is_active=True,
        membership__institution__is_active=True, membership__institution__university__is_active=True)
    rows = rows.filter(Q(campus__isnull=True) | Q(campus__institution=F('membership__institution')))
    rows = rows.filter(Q(department__isnull=True) | Q(department__campus=F('campus')))
    if institution_id is not None:
        rows = rows.filter(membership__institution_id=institution_id)
    return rows.select_related('membership', 'campus', 'department')


def permitted(actor, model, action):
    if not enabled(actor) or action == 'delete':
        return False
    if actor.is_superuser:
        return True
    if model._meta.model_name != 'timeslot' and action != 'view':
        return False
    return actor.has_perm(f'academic_calendar.{action}_{model._meta.model_name}')


def campuses(actor, *, write=False, institution_id=None):
    query = Campus.objects.select_related('institution__university')
    if not enabled(actor):
        return query.none()
    if actor.is_superuser:
        return query.filter(institution_id=institution_id) if institution_id is not None else query
    visible = Q(pk__in=[])
    for grant in grants(actor, institution_id):
        if write and grant.role not in ('INSTITUTION_ADMIN', 'CAMPUS_ADMIN'):
            continue
        part = Q(institution_id=grant.membership.institution_id)
        if grant.campus_id:
            part &= Q(pk=grant.campus_id)
        if not isinstance(grant.record_limits, dict):
            continue
        limits = grant.record_limits.get('campuses')
        if limits is not None:
            if not isinstance(limits, list) or any(type(x) is not int or x < 1 for x in limits):
                continue
            part &= Q(pk__in=limits[:500])
        if not write and grant.role not in ('INSTITUTION_ADMIN', 'CAMPUS_ADMIN'):
            part &= Q(is_active=True)
        visible |= part
    return query.filter(visible)


def scoped(model, actor, *, action='view', institution_id=None):
    query = model.objects.all()
    if not permitted(actor, model, action):
        return query.none()
    if actor.is_superuser:
        if model._meta.model_name == 'timeslot' and institution_id is not None:
            return query.filter(campus__institution_id=institution_id)
        return query
    if model._meta.model_name != 'timeslot':
        return query if grants(actor, institution_id).exists() else query.none()
    write = action != 'view'
    visible = Q(pk__in=[])
    for grant in grants(actor, institution_id):
        if write and grant.role not in ('INSTITUTION_ADMIN', 'CAMPUS_ADMIN'):
            continue
        part = Q(campus__institution_id=grant.membership.institution_id)
        if grant.campus_id:
            part &= Q(campus_id=grant.campus_id)
        if not isinstance(grant.record_limits, dict):
            continue
        for key, lookup in [('campuses', 'campus_id__in'), ('time-slots', 'pk__in')]:
            ids = grant.record_limits.get(key)
            if ids is not None:
                if not isinstance(ids, list) or any(type(x) is not int or x < 1 for x in ids):
                    part &= Q(pk__in=[])
                else:
                    part &= Q(**{lookup: ids[:500]})
        if not write and grant.role not in ('INSTITUTION_ADMIN', 'CAMPUS_ADMIN'):
            part &= Q(campus__is_active=True)
        visible |= part
    return query.filter(visible).select_related('campus__institution__university')


def can_create(actor, model):
    if not permitted(actor, model, 'add'):
        return False
    return actor.is_superuser or campuses(actor, write=True).exists()
