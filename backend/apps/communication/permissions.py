from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.admission_enrolment.models import StudentProgrammeEnrolment
from apps.organization.models import Department, Institution
from apps.people_master.models import AccountLink, EmployeeAssignment
from apps.tenancy.models import Membership, ScopeGrant

from . import models as m


def enabled(actor):
    return settings.COMMUNICATION_ENABLED and actor.is_authenticated and actor.is_active


def can(actor, capability):
    return enabled(actor) and (
        actor.is_superuser or actor.has_perm("communication." + capability)
    )


def memberships(actor):
    qs = Membership.objects.filter(
        user=actor,
        is_active=True,
        institution_id__in=settings.COMMUNICATION_INSTITUTIONS,
        institution__is_active=True,
        institution__university__is_active=True,
    )
    return qs if enabled(actor) else qs.none()


def grants(actor):
    return (
        ScopeGrant.objects.filter(membership__in=memberships(actor), is_active=True)
        .exclude(role="STUDENT")
        .filter(
            Q(campus__isnull=True)
            | Q(campus__institution_id=F("membership__institution_id"))
        )
        .filter(Q(department__isnull=True) | Q(department__campus_id=F("campus_id")))
        .select_related("membership")
    )


def institutions(actor):
    qs = Institution.objects.filter(
        pk__in=settings.COMMUNICATION_INSTITUTIONS,
        is_active=True,
        university__is_active=True,
    )
    if not enabled(actor):
        return qs.none()
    return (
        qs
        if actor.is_superuser
        else qs.filter(pk__in=memberships(actor).values("institution_id"))
    )


def scope(actor, capability):
    if not can(actor, capability):
        return Q(pk__in=[])
    base = Q(institution__in=institutions(actor))
    if actor.is_superuser:
        return base
    condition = Q(pk__in=[])
    for g in grants(actor):
        if g.record_limits:
            continue
        part = Q(institution_id=g.membership.institution_id)
        if g.campus_id:
            part &= Q(
                department__campus_id=g.campus_id, department__campus__is_active=True
            )
        if g.department_id:
            part &= Q(department_id=g.department_id, department__is_active=True)
        condition |= part
    return base & condition


def management(actor, capability="review_announcement"):
    return m.Announcement.objects.filter(scope(actor, capability))


def get(qs, pk, lock=False):
    obj = (qs.select_for_update() if lock else qs).filter(pk=pk).first()
    if obj is None:
        raise NotFound("Announcement unavailable.")
    return obj


def authorize_scope(actor, institution_id, department_id, capability):
    if (
        not can(actor, capability)
        or not institutions(actor).filter(pk=institution_id).exists()
    ):
        raise NotFound()
    if (
        department_id is not None
        and not Department.objects.filter(
            pk=department_id,
            campus__institution_id=institution_id,
            is_active=True,
            campus__is_active=True,
        ).exists()
    ):
        raise NotFound()
    if department_id is None and not can(actor, "publish_institution"):
        raise PermissionDenied("Institution-wide publishing authority required.")
    if actor.is_superuser:
        return
    for g in grants(actor):
        if g.record_limits or g.membership.institution_id != institution_id:
            continue
        if not g.campus_id and not g.department_id:
            return
        if (
            department_id
            and (not g.department_id or department_id == g.department_id)
            and Department.objects.filter(
                pk=department_id, **({"campus_id": g.campus_id} if g.campus_id else {})
            ).exists()
        ):
            return
    raise NotFound()


def recipients(actor, at=None):
    if not enabled(actor):
        return m.Announcement.objects.none()
    member_ids = memberships(actor).values("institution_id")
    students = AccountLink.objects.filter(
        user=actor,
        student__institution_id__in=member_ids,
        student__student_status="ACTIVE",
    )
    staff = AccountLink.objects.filter(
        user=actor,
        employee__institution_id__in=member_ids,
        employee__employment_status="ACTIVE",
    )
    student_institutions = students.values("student__institution_id")
    staff_institutions = staff.values("employee__institution_id")
    today = timezone.localdate(at or timezone.now())
    assignments = EmployeeAssignment.objects.filter(
        employee_id__in=staff.values("employee_id"),
        start_date__lte=today,
        campus__institution_id=F("employee__institution_id"),
        department__campus_id=F("campus_id"),
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
    departments = list(
        students.values_list("student__department_id", flat=True)
    ) + list(assignments.values_list("department_id", flat=True))
    programmes = StudentProgrammeEnrolment.objects.filter(
        student_id__in=students.values("student_id"),
        enrolment_status="ACTIVE",
        admission_date__lte=today,
        student__institution_id=F("programme__department__campus__institution_id"),
        programme__department__campus__is_active=True,
        programme__is_active=True,
        programme__department__is_active=True,
    ).values("programme_id")
    audience = (
        Q(audience_type="ALL")
        | Q(audience_type="STUDENTS", institution_id__in=student_institutions)
        | Q(audience_type="STAFF", institution_id__in=staff_institutions)
        | Q(
            audience_type="DEPARTMENT",
            department_id__in=departments,
            department__campus__institution_id=F("institution_id"),
            department__is_active=True,
            department__campus__is_active=True,
        )
        | Q(
            audience_type="PROGRAMME",
            programme_targets__programme_id__in=programmes,
            programme_targets__programme__department__campus__institution_id=F(
                "institution_id"
            ),
        )
        | Q(audience_type="CUSTOM", user_targets__user=actor)
    )
    return (
        m.Announcement.objects.filter(institution_id__in=member_ids)
        .filter(audience)
        .distinct()
    )


def type_admin(actor):
    if not can(actor, "manage_types") or not (
        actor.is_superuser or actor.has_perm("accounts.manage_platform_access")
    ):
        raise PermissionDenied()


def department_choices(actor, institution_id):
    if not institutions(actor).filter(pk=institution_id).exists() or not (
        can(actor, "create_announcement") or can(actor, "edit_announcement")
    ):
        return Department.objects.none()
    rows = Department.objects.filter(
        campus__institution_id=institution_id, is_active=True, campus__is_active=True
    )
    if actor.is_superuser:
        return rows
    condition = Q(pk__in=[])
    for g in grants(actor):
        if g.record_limits or g.membership.institution_id != institution_id:
            continue
        part = Q()
        if g.campus_id:
            part &= Q(campus_id=g.campus_id)
        if g.department_id:
            part &= Q(pk=g.department_id)
        if not g.campus_id and not g.department_id:
            return rows
        condition |= part
    return rows.filter(condition)
