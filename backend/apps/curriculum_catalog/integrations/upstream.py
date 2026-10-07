from dataclasses import dataclass
from django.db.models import Q, F
from rest_framework.exceptions import PermissionDenied, NotFound

# Declared integration adapter: the only runtime organization/tenancy ORM boundary.
from apps.organization.models import Department, Programme, ProgrammeSpecialization
from apps.tenancy.models import ScopeGrant
from apps.academic_calendar.public import semesters


@dataclass(frozen=True)
class OrganizationContext:
    id: int
    institution_id: int
    campus_id: int
    department_id: int
    active: bool
    duration_semesters: int | None = None
    programme_id: int | None = None


def grants(actor):
    return (
        ScopeGrant.objects.filter(
            membership__user=actor,
            membership__is_active=True,
            is_active=True,
            membership__institution__is_active=True,
            membership__institution__university__is_active=True,
            membership__institution__institutionmodule__curriculum_catalog=True,
        )
        .filter(
            Q(campus__isnull=True) | Q(campus__institution=F("membership__institution"))
        )
        .filter(Q(department__isnull=True) | Q(department__campus=F("campus")))
        .select_related("membership", "campus", "department")
    )


def organization_rows(kind, actor, write=False):
    models = {
        "departments": Department,
        "programmes": Programme,
        "specializations": ProgrammeSpecialization,
    }
    model = models[kind]
    chain = (
        ""
        if kind == "departments"
        else "department__"
        if kind == "programmes"
        else "programme__department__"
    )
    query = model.objects.select_related(chain + "campus__institution__university")
    if not actor or not actor.is_authenticated or not actor.is_active:
        return query.none()
    if actor.is_superuser:
        return query
    visibility = Q(pk__in=[])
    for grant in grants(actor):
        if write and grant.role in ("TEACHER", "STUDENT"):
            continue
        part = Q(**{chain + "campus__institution_id": grant.membership.institution_id})
        if grant.campus_id:
            part &= Q(**{chain + "campus_id": grant.campus_id})
        if grant.department_id:
            part &= Q(**{chain + "pk": grant.department_id})
        if not isinstance(grant.record_limits, dict):
            continue
        for key, lookup in [
            ("campuses", chain + "campus_id__in"),
            ("departments", chain + "pk__in"),
            *(
                [("programmes", "pk__in")]
                if kind == "programmes"
                else [
                    ("programmes", "programme_id__in"),
                    ("programme-specializations", "pk__in"),
                ]
                if kind == "specializations"
                else []
            ),
        ]:
            ids = grant.record_limits.get(key)
            if ids is not None:
                if not isinstance(ids, list) or any(
                    type(value) is not int or value < 1 for value in ids
                ):
                    part &= Q(pk__in=[])
                else:
                    part &= Q(**{lookup: ids[:500]})
        visibility |= part
    return query.filter(visibility)


def describe(kind, row):
    programme = (
        row
        if kind == "programmes"
        else row.programme
        if kind == "specializations"
        else None
    )
    department = row if kind == "departments" else programme.department
    campus = department.campus
    active = all(
        (
            row.is_active,
            department.is_active,
            campus.is_active,
            campus.institution.is_active,
            campus.institution.university.is_active,
        )
    )
    if programme:
        active = active and programme.is_active
    return OrganizationContext(
        row.pk,
        campus.institution_id,
        campus.pk,
        department.pk,
        active,
        programme.duration_semesters if programme else None,
        programme.pk if programme else None,
    )


def lookup(kind, pk, *, actor, write=False):
    row = organization_rows(kind, actor, write).filter(pk=pk).first()
    if row is None:
        raise NotFound("Parent is unavailable in your scope.")
    return describe(kind, row)


def semester_map(*, actor, institution_id):
    rows = semesters(actor=actor, institution_id=institution_id)
    if not rows:
        raise PermissionDenied(
            "Calendar access and semester reference data are required."
        )
    return {pk: (number, name) for pk, number, name in rows}
