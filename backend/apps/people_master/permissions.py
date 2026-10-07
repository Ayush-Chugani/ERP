from django.conf import settings
from django.db.models import Q
from rest_framework.permissions import BasePermission
from . import models as m
from .catalogue import SHARED, PATHS
from .integrations.upstream import grants


class PeopleModuleEnabled(BasePermission):
    def has_permission(self, request, view):
        return enabled(request.user)


def enabled(actor):
    return bool(
        getattr(settings, "PEOPLE_MASTER_ENABLED", False)
        and actor
        and actor.is_authenticated
        and actor.is_active
    )


def permitted(actor, model, action="view"):
    return enabled(actor) and (
        actor.is_superuser
        or actor.has_perm(f"people_master.{action}_{model._meta.model_name}")
    )


def root_info(model):
    if model in (m.Student, m.Employee, m.ExternalAgency):
        return model, ""
    if model in (
        m.StudentAddress,
        m.StudentParentGuardian,
        m.StudentResidence,
        m.StudentPreviousEducation,
        m.StudentEntranceExam,
    ):
        return m.Student, "student__"
    if model in (m.EmployeeAddress, m.EmployeeAssignment, m.EmployeeCompetency):
        return m.Employee, "employee__"
    return None, ""


def scoped(model, actor, action="view"):
    query = model.objects.all()
    if not permitted(actor, model, action):
        return query.none()
    if actor.is_superuser:
        return query
    rows = list(grants(actor))
    if model in SHARED:
        return query if action == "view" and rows else query.none()
    root, prefix = root_info(model)
    if root is None:
        return query.none()
    condition = Q(pk__in=[])
    for g in rows:
        if g.role in ("TEACHER", "STUDENT"):
            continue
        part = Q(**{prefix + "institution_id": g.membership.institution_id})
        if root is m.Student:
            if g.campus_id:
                part &= Q(**{prefix + "campus_id": g.campus_id})
            if g.department_id:
                part &= Q(**{prefix + "department_id": g.department_id})
        elif root is m.Employee and (g.campus_id or g.department_id):
            assignments = m.EmployeeAssignment.objects.filter(
                is_primary=True, end_date__isnull=True
            )
            if g.campus_id:
                assignments = assignments.filter(campus_id=g.campus_id)
            if g.department_id:
                assignments = assignments.filter(department_id=g.department_id)
            part &= Q(**{prefix + "pk__in": assignments.values("employee_id")})
        elif root is m.ExternalAgency and (g.campus_id or g.department_id):
            continue
        limits = g.record_limits
        if not isinstance(limits, dict):
            continue
        for key, lookup in [
            (
                PATHS[model],
                "employee_id__in" if model is m.EmployeeCompetency else "pk__in",
            ),
            (PATHS[root], prefix + "pk__in"),
        ]:
            if key in limits:
                values = limits[key]
                if not isinstance(values, list) or any(
                    type(v) is not int or v < 1 for v in values
                ):
                    part &= Q(pk__in=[])
                else:
                    part &= Q(**{lookup: values[:500]})
        condition |= part
    # A verified link narrows access; it never bypasses grant record limits.
    if action == "view" and root in (m.Student, m.Employee):
        name = "student" if root is m.Student else "employee"
        own = m.AccountLink.objects.filter(user=actor).values_list(
            name + "_id", flat=True
        )
        for g in rows:
            part = Q(
                **{
                    prefix + "pk__in": own,
                    prefix + "institution_id": g.membership.institution_id,
                }
            )
            limits = g.record_limits
            if not isinstance(limits, dict):
                continue
            for resource_name, lookup in [
                (PATHS[root], prefix + "pk__in"),
                (
                    PATHS[model],
                    "employee_id__in" if model is m.EmployeeCompetency else "pk__in",
                ),
            ]:
                if resource_name in limits:
                    part &= Q(**{lookup: limits[resource_name]})
            condition |= part
    # Meta.ordering = ["pk"] breaks SELECT DISTINCT on composite keys; callers order explicitly.
    return query.filter(condition).distinct().order_by()


def owner(obj):
    root, prefix = root_info(type(obj))
    return getattr(obj, prefix[:-2]) if prefix else obj


def institution_id(obj):
    return getattr(owner(obj), "institution_id", None)


def related(query):
    fields = [
        f.name for f in query.model._meta.fields if f.is_relation and f.many_to_one
    ]
    return query.select_related(*fields)
