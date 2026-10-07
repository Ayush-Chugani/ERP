"""Scope-aware reads used by downstream employee-assignment consumers."""

from .models import EmployeeAssignment
from .permissions import scoped, related


def current_assignments(*, actor, institution_id, employee_id):
    return (
        related(scoped(EmployeeAssignment, actor))
        .filter(
            employee_id=employee_id,
            employee__institution_id=institution_id,
            is_primary=True,
            end_date__isnull=True,
        )
        .order_by("start_date", "pk")
    )
