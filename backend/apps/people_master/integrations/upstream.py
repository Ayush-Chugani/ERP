"""The declared organization and membership integration boundary."""

from django.db.models import Q, F
from apps.tenancy.models import ScopeGrant, Membership
from apps.organization.models import Institution, Campus, Department


def grants(actor):
    return (
        ScopeGrant.objects.filter(
            membership__user=actor,
            membership__is_active=True,
            is_active=True,
            membership__institution__is_active=True,
            membership__institution__university__is_active=True,
            membership__institution__institutionmodule__people_master=True,
        )
        .filter(
            Q(campus__isnull=True) | Q(campus__institution=F("membership__institution"))
        )
        .filter(Q(department__isnull=True) | Q(department__campus=F("campus")))
        .select_related("membership", "campus", "department")
    )


def context(actor, institution_id, campus_id=None, department_id=None, write=False):
    from rest_framework.exceptions import PermissionDenied

    if not actor.is_active or not actor.is_authenticated:
        raise PermissionDenied()
    institution = Institution.objects.filter(
        pk=institution_id, is_active=True, university__is_active=True
    ).first()
    if not institution:
        raise PermissionDenied("Institution unavailable.")
    if (
        campus_id
        and not Campus.objects.filter(
            pk=campus_id, institution_id=institution_id, is_active=True
        ).exists()
    ):
        raise PermissionDenied("Campus unavailable.")
    if department_id and (
        not campus_id
        or not Department.objects.filter(
            pk=department_id, campus_id=campus_id, is_active=True
        ).exists()
    ):
        raise PermissionDenied("Department unavailable.")
    if actor.is_superuser:
        return
    for grant in grants(actor):
        if write and grant.role in ("TEACHER", "STUDENT"):
            continue
        if grant.membership.institution_id != institution_id:
            continue
        if grant.campus_id and grant.campus_id != campus_id:
            continue
        if grant.department_id and grant.department_id != department_id:
            continue
        limits = grant.record_limits
        if not isinstance(limits, dict):
            continue
        if any(
            key in limits and value not in limits[key]
            for key, value in [
                ("institutions", institution_id),
                ("campuses", campus_id),
                ("departments", department_id),
            ]
        ):
            continue
        return
    raise PermissionDenied("No matching institution scope.")


def course_choices(model, actor):
    """Declared queryset adapter solely for scoped autocomplete."""
    from apps.curriculum_catalog.policies import scoped

    return scoped(model, actor)
