"""M16 owns employee policy; M15 remains the permission decision owner."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from apps.identity_access.evaluator import Scope, has_object_permission


def require_enabled():
    if not settings.EMPLOYEE_HR_ENABLED:
        raise NotFound()


def require_permission(actor, code, *, scopes):
    require_enabled()
    if (not actor or not getattr(actor, 'is_authenticated', False)
            or not settings.IDENTITY_ACCESS_ENABLED or not settings.IDENTITY_ACCESS_SECURITY_ENABLED):
        raise PermissionDenied()
    # Re-read forced-reset state: a previously loaded actor is not authoritative.
    actor = get_user_model().objects.filter(pk=actor.pk).first()
    if (actor is None or actor.must_change_password
            or not has_object_permission(actor, code, scopes=scopes)):
        raise PermissionDenied()


def require_employee_permission(actor, code, *, employee_id):
    """Resolve row ancestry from stored ownership, never caller-supplied scopes.

    Assignment dates are inclusive, as in the people-master date contract.
    Call inside the owning write transaction when changing employee records.
    This grants no document ACL, decrypt or download permission by itself.
    """
    from apps.people_master.models import Employee, EmployeeAssignment, AccountLink

    require_enabled()
    if not actor or not getattr(actor, 'is_authenticated', False):
        raise PermissionDenied()
    if type(employee_id) is not int or employee_id <= 0:
        raise PermissionDenied()
    employee = Employee.objects.filter(pk=employee_id).first()
    if employee is None:
        raise PermissionDenied()
    scopes = {Scope('GLOBAL', 0), Scope('INSTITUTION', employee.institution_id)}
    today = timezone.localdate()
    assignments = EmployeeAssignment.objects.filter(
        employee_id=employee_id, start_date__lte=today,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).select_related('campus', 'department')
    for assignment in assignments:
        # A corrupt cross-institution assignment cannot confer broader access.
        if (assignment.campus.institution_id != employee.institution_id
                or (assignment.department_id and assignment.department.campus_id != assignment.campus_id)):
            raise PermissionDenied()
        scopes.add(Scope('CAMPUS', assignment.campus_id))
        if assignment.department_id:
            scopes.add(Scope('DEPARTMENT', assignment.department_id))
    owner_user_id = AccountLink.objects.filter(employee_id=employee_id).values_list('user_id', flat=True).first()
    if owner_user_id is not None:
        scopes.add(Scope('SELF', owner_user_id))
    require_permission(actor, code, scopes=scopes)
    return employee
