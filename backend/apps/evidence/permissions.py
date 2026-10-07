from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.identity_access.evaluator import Scope, evidence, has_object_permission
from apps.identity_access.models import Permission
from apps.people_master.models import AccountLink


def principal(actor):
    if not settings.EVIDENCE_ENABLED:
        raise NotFound()
    if (
        not settings.IDENTITY_ACCESS_ENABLED
        or not settings.IDENTITY_ACCESS_SECURITY_ENABLED
        or not actor
        or not actor.is_authenticated
    ):
        raise PermissionDenied()
    fresh = get_user_model().objects.filter(pk=actor.pk, is_active=True).first()
    if fresh is None or fresh.must_change_password:
        raise PermissionDenied()
    return fresh


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
        f"EVIDENCE.{resource}.{action}",
        scopes=scopes(parent) if parent else [Scope("GLOBAL", 0)],
    ):
        raise PermissionDenied()
    return actor


def scope(actor, resource="DOCUMENT", action="READ", prefix="staff_activity__"):
    actor = principal(actor)
    code = f"EVIDENCE.{resource}.{action}"
    if not Permission.objects.filter(
        permission_code=code,
        is_active=True,
        access_resource__is_active=True,
        access_resource__access_module__is_active=True,
        access_action__is_active=True,
    ).exists():
        return Q(pk__in=[])
    allow, deny = Q(pk__in=[]), Q(pk__in=[])
    paths = {
        "INSTITUTION": prefix + "institution_id",
        "CAMPUS": prefix + "campus_id",
        "DEPARTMENT": prefix + "department_id",
        "SELF": prefix + "employee__accountlink__user_id",
    }
    for permission in (code, f"EVIDENCE.ALL.{action}"):
        for item in evidence(actor, permission):
            which = item["scope"]
            condition = (
                Q(pk__isnull=False)
                if which.kind == "GLOBAL"
                else Q(**{paths[which.kind]: which.entity_id})
                if which.kind in paths
                else Q(pk__in=[])
            )
            if item["effect"] == "ALLOW":
                allow |= condition
            else:
                deny |= condition
    return allow & ~deny


def classification_scope(actor):
    allowed = Q(pk__in=[])
    for code, storage_level in settings.EVIDENCE_CLASSIFICATIONS.items():
        if storage_level not in {
            "PUBLIC",
            "INTERNAL",
            "RESTRICTED",
            "CONFIDENTIAL",
            "HIGHLY_RESTRICTED",
        }:
            continue
        part = Q(
            confidentiality_level__level_code=code,
            confidentiality_level__is_active=True,
        )
        if storage_level not in {"PUBLIC", "INTERNAL"}:
            part &= scope(actor, "LEVEL_" + code)
        allowed |= part
    return allowed


def classification(actor, level, parent):
    code = level.level_code
    mapped = settings.EVIDENCE_CLASSIFICATIONS.get(code)
    if not level.is_active or mapped not in {
        "PUBLIC",
        "INTERNAL",
        "RESTRICTED",
        "CONFIDENTIAL",
        "HIGHLY_RESTRICTED",
    }:
        raise PermissionDenied()
    if mapped not in {"PUBLIC", "INTERNAL"}:
        require(actor, "LEVEL_" + code, "READ", parent)
    return mapped


def document(actor, row, resource="DOCUMENT", action="READ", deleted=False):
    parent = row.staff_activity
    if parent.deleted_at or (not deleted and (row.deleted_at or not row.is_active)):
        raise NotFound()
    actor = require(actor, "DOCUMENT", "READ", parent)
    classification(actor, row.confidentiality_level, parent)
    require(actor, resource, action, parent)
    return actor
