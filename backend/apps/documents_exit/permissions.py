from django.conf import settings
from django.db.models import F, Q
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.organization.models import Department
from apps.people_master.models import AccountLink, Student
from apps.tenancy.models import Membership, ScopeGrant

from . import models as m


def can(actor, capability):
    return bool(
        settings.DOCUMENTS_EXIT_ENABLED
        and actor.is_authenticated
        and actor.is_active
        and (actor.is_superuser or actor.has_perm("documents_exit." + capability))
    )


def memberships(actor):
    qs = Membership.objects.filter(
        user=actor,
        is_active=True,
        institution__is_active=True,
        institution__university__is_active=True,
    )
    return qs.filter(institution_id__in=settings.DOCUMENTS_EXIT_INSTITUTIONS)


def identity(actor, kind, active=False):
    if (
        not settings.DOCUMENTS_EXIT_ENABLED
        or not actor.is_authenticated
        or not actor.is_active
    ):
        raise NotFound()
    qs = AccountLink.objects.filter(
        user=actor,
        **{kind + "__institution_id__in": memberships(actor).values("institution_id")},
    ).select_related(kind)
    if active:
        qs = qs.filter(
            **{
                kind
                + "__"
                + (
                    "student_status" if kind == "student" else "employment_status"
                ): "ACTIVE"
            }
        )
    row = qs.first()
    if row is None:
        raise NotFound("Support record unavailable.")
    return getattr(row, kind)


def grants(actor):
    return (
        ScopeGrant.objects.filter(membership__in=memberships(actor), is_active=True)
        .exclude(role="STUDENT")
        .filter(
            Q(campus__isnull=True)
            | Q(campus__institution_id=F("membership__institution_id"))
        )
        .filter(Q(department__isnull=True) | Q(department__campus_id=F("campus_id")))
    )


def scope(actor, capability, institution_path, department_path):
    if not can(actor, capability):
        return Q(pk__in=[])
    if actor.is_superuser:
        return Q(
            **{
                institution_path + "__is_active": True,
                institution_path + "__university__is_active": True,
            }
        )
    result = Q(pk__in=[])
    for grant in grants(actor):
        # Unrecognized/record-limited grants fail closed instead of broadening access.
        if grant.record_limits:
            continue
        part = Q(**{institution_path + "_id": grant.membership.institution_id})
        if grant.campus_id:
            part &= Q(
                **{
                    department_path + "__campus_id": grant.campus_id,
                    department_path + "__campus__is_active": True,
                }
            )
        if grant.department_id:
            part &= Q(
                **{
                    department_path + "_id": grant.department_id,
                    department_path + "__is_active": True,
                }
            )
        result |= part
    return result


def students(actor, capability):
    return Student.objects.filter(scope(actor, capability, "institution", "department"))


def department_allowed(actor, pk, capability, institution_id):
    if not can(actor, capability):
        return False
    if (
        pk is not None
        and not Department.objects.filter(
            pk=pk,
            campus__institution_id=institution_id,
            is_active=True,
            campus__is_active=True,
        ).exists()
    ):
        return False
    if actor.is_superuser:
        return True
    for grant in grants(actor):
        if grant.record_limits or grant.membership.institution_id != institution_id:
            continue
        if pk is None:
            if not grant.campus_id and not grant.department_id:
                return True
            continue
        if Department.objects.filter(
            pk=pk,
            **({"campus_id": grant.campus_id} if grant.campus_id else {}),
            **({"department_id": grant.department_id} if grant.department_id else {}),
        ).exists():
            return True
    return False


def get(qs, pk, lock=False):
    if lock:
        qs = qs.select_for_update()
    obj = qs.filter(pk=pk).first()
    if obj is None:
        raise NotFound("Document record unavailable.")
    return obj


def scoped(model, actor, capability=None, own_cap=None):
    prefix = "enrolment__student" if model is m.StudentExit else "student"
    cond = (
        scope(actor, capability, prefix + "__institution", prefix + "__department")
        if capability
        else Q(pk__in=[])
    )
    if own_cap and can(actor, own_cap):
        try:
            cond |= Q(**{prefix: identity(actor, "student")})
        except NotFound:
            pass
    return model.objects.filter(cond)


def own_student(actor, capability):
    if not can(actor, capability):
        raise NotFound()
    return identity(actor, "student", True)


def reject_self_approval(actor, student_id):
    if AccountLink.objects.filter(user=actor, student_id=student_id).exists():
        raise PermissionDenied("Self approval and issuance are not permitted.")


def file_level(actor, obj):
    if obj.deleted_at:
        raise NotFound()
    if obj.confidentiality_level == "HIGHLY_RESTRICTED" and not can(
        actor, "access_highly_restricted_file"
    ):
        raise NotFound()
    if obj.confidentiality_level == "RESTRICTED" and not can(
        actor, "access_restricted_file"
    ):
        raise NotFound()


def type_admin(actor):
    if not can(actor, "manage_certificate_type") or not (
        actor.is_superuser or actor.has_perm("accounts.manage_platform_access")
    ):
        raise PermissionDenied()
