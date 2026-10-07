from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.identity_access.evaluator import Scope, evidence, has_object_permission
from apps.identity_access.models import Permission
from apps.people_master.models import AccountLink


def principal(actor):
    if not settings.AWARDS_ENABLED:
        raise NotFound()
    if (
        not settings.IDENTITY_ACCESS_ENABLED
        or not settings.IDENTITY_ACCESS_SECURITY_ENABLED
    ):
        raise PermissionDenied()
    if not actor or not actor.is_authenticated:
        raise PermissionDenied()
    actor = get_user_model().objects.filter(pk=actor.pk).first()
    if actor is None or actor.must_change_password:
        raise PermissionDenied()
    return actor


def scopes(parent):
    result = [Scope("GLOBAL", 0), Scope("INSTITUTION", parent.institution_id)]
    if parent.campus_id:
        result.append(Scope("CAMPUS", parent.campus_id))
    if parent.department_id:
        result.append(Scope("DEPARTMENT", parent.department_id))
    owner = (
        AccountLink.objects.filter(employee_id=parent.employee_id)
        .values_list("user_id", flat=True)
        .first()
    )
    if owner:
        result.append(Scope("SELF", owner))
    return result


def require(actor, resource, action, parent=None):
    actor = principal(actor)
    if not has_object_permission(
        actor,
        f"AWARDS.{resource}.{action}",
        scopes=scopes(parent) if parent else [Scope("GLOBAL", 0)],
    ):
        raise PermissionDenied()
    return actor


def activity_scope(actor, action="READ", paths=None):
    actor = principal(actor)
    code = f"AWARDS.ACTIVITY.{action}"
    if not Permission.objects.filter(
        permission_code=code,
        is_active=True,
        access_resource__is_active=True,
        access_resource__access_module__is_active=True,
        access_action__is_active=True,
    ).exists():
        return Q(pk__in=[])
    allow, deny = Q(pk__in=[]), Q(pk__in=[])
    paths = paths or {
        "INSTITUTION": "staff_activity__institution_id",
        "CAMPUS": "staff_activity__campus_id",
        "DEPARTMENT": "staff_activity__department_id",
        "SELF": "staff_activity__employee__accountlink__user_id",
    }
    for permission in (code, f"AWARDS.ALL.{action}"):
        for row in evidence(actor, permission):
            scope = row["scope"]
            if scope.kind == "GLOBAL":
                condition = Q(pk__isnull=False)
            elif scope.kind in paths:
                condition = Q(**{paths[scope.kind]: scope.entity_id})
            else:
                continue
            if row["effect"] == "ALLOW":
                allow |= condition
            else:
                deny |= condition
    return allow & ~deny
