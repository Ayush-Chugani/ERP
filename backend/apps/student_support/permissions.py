from django.conf import settings
from django.db.models import F, Q
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.organization.models import Department
from apps.people_master.models import AccountLink, Student
from apps.tenancy.models import Membership, ScopeGrant

from . import models as m
from . import policies


def can(actor, capability):
    return bool(
        settings.STUDENT_SUPPORT_ENABLED
        and actor.is_authenticated
        and actor.is_active
        and (actor.is_superuser or actor.has_perm("student_support." + capability))
    )


def memberships(actor):
    qs = Membership.objects.filter(
        user=actor,
        is_active=True,
        institution__is_active=True,
        institution__university__is_active=True,
    )
    return qs.filter(institution_id__in=settings.STUDENT_SUPPORT_INSTITUTIONS)


def identity(actor, kind, active=False):
    if (
        not settings.STUDENT_SUPPORT_ENABLED
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


def assignments(actor, capability=None):
    qs = m.MentorAssignment.objects.select_related("student", "employee")
    if capability:
        return qs.filter(
            scope(actor, capability, "student__institution", "student__department")
        )
    cond = scope(
        actor,
        "manage_mentor_assignments",
        "student__institution",
        "student__department",
    )
    try:
        employee = identity(actor, "employee", True)
        cond |= Q(employee=employee, student__institution_id=employee.institution_id)
    except NotFound:
        pass
    try:
        student = identity(actor, "student")
        if policies.policy(student.institution_id, "student_assignment_read", True):
            cond |= Q(student=student)
    except NotFound:
        pass
    return qs.filter(cond)


def sessions(actor, write=False):
    qs = m.CounsellingSession.objects.select_related(
        "mentor_assignment__student", "mentor_assignment__employee"
    )
    if not settings.STUDENT_SUPPORT_ENABLED:
        return qs.none()
    cond = Q(pk__in=[])
    if actor.is_superuser and actor.is_active:
        cond = scope(
            actor,
            "conduct_counselling",
            "mentor_assignment__student__institution",
            "mentor_assignment__student__department",
        )
    else:
        if not write or can(actor, "conduct_counselling"):
            try:
                employee = identity(actor, "employee", True)
                cond |= Q(
                    mentor_assignment__employee=employee,
                    mentor_assignment__student__institution_id=employee.institution_id,
                )
            except NotFound:
                pass
            cond |= scope(
                actor,
                "view_counselling_all",
                "mentor_assignment__student__institution",
                "mentor_assignment__student__department",
            )
        if not write and can(actor, "view_counselling_normal"):
            try:
                student = identity(actor, "student")
                if policies.policy(
                    student.institution_id, "student_normal_notes", True
                ):
                    cond |= Q(
                        mentor_assignment__student=student,
                        confidentiality_level="NORMAL",
                    )
            except NotFound:
                pass
    levels = [
        level
        for level in policies.LEVELS
        if can(actor, "view_counselling_" + level.lower())
    ]
    if write and not can(actor, "conduct_counselling"):
        return qs.none()
    return qs.filter(cond, confidentiality_level__in=levels)


def grievances(actor, capability=None, own=False):
    qs = m.Grievance.objects.select_related(
        "student", "grievance_category", "department"
    )
    cond = Q(pk__in=[])
    if not own:
        caps = (
            [capability]
            if capability
            else [
                "view_grievance_queue",
                "triage_grievance",
                "resolve_grievance",
                "close_grievance",
            ]
        )
        for cap in caps:
            cond |= scope(actor, cap, "student__institution", "department")
    if not capability and can(actor, "view_own_grievance"):
        try:
            cond |= Q(student=identity(actor, "student"))
        except NotFound:
            pass
    return qs.filter(cond)


def get(qs, pk, lock=False):
    if lock:
        qs = qs.select_for_update()
    obj = qs.filter(pk=pk).first()
    if obj is None:
        raise NotFound("Support record unavailable.")
    return obj


def category_admin(actor):
    if not can(actor, "manage_grievance_categories") or not (
        actor.is_superuser or actor.has_perm("accounts.manage_platform_access")
    ):
        raise PermissionDenied()
