"""Immutable, purpose-limited read contracts for other modules."""

from dataclasses import dataclass
from rest_framework.exceptions import PermissionDenied, NotFound
from . import models as m
from .permissions import scoped, enabled
from .services import audit


def admission_student(*, actor, institution_id, student_id):
    """Governed M6 integration: explicitly selected, visible, active student."""
    from .services import activation_ready
    row = scoped(m.Student, actor).select_for_update().filter(pk=student_id, institution_id=institution_id).first()
    if row is None:
        raise NotFound('Student unavailable.')
    if row.student_status != 'ACTIVE':
        from rest_framework.exceptions import ValidationError
        raise ValidationError('Activate the student in People before admission.')
    activation_ready(row)
    audit(row, actor, 'read', {}, source='integration')
    return row


@dataclass(frozen=True)
class PersonIdentity:
    id: str
    institution_id: str
    number: str
    display_name: str
    status: str


def identity(*, actor, institution_id, kind, record_id):
    model = {"student": m.Student, "employee": m.Employee}.get(kind)
    if model is None:
        raise NotFound()
    row = (
        scoped(model, actor).filter(pk=record_id, institution_id=institution_id).first()
    )
    if not row:
        raise NotFound()
    audit(row, actor, "read", {}, source="integration")
    return PersonIdentity(
        str(row.pk),
        str(row.institution_id),
        getattr(row, kind + "_number"),
        row.display_name,
        getattr(row, "student_status" if kind == "student" else "employment_status"),
    )


def events(*, actor, institution_id, after_audit_id=0, limit=100):
    if not enabled(actor) or not actor.is_superuser:
        raise PermissionDenied()
    rows = m.PeopleEvent.objects.filter(
        audit__institution_id=institution_id, audit_id__gt=after_audit_id
    ).order_by("audit_id")[: max(1, min(limit, 100))]
    return tuple(
        {
            "id": str(row.pk),
            "cursor": str(row.audit_id),
            "type": row.event_type,
            "version": row.schema_version,
            "payload": row.payload,
        }
        for row in rows
    )


@dataclass(frozen=True)
class AssignmentIdentity:
    id: str
    employee_id: str
    campus_id: str
    department_id: str | None
    designation_id: str


def current_assignment(*, actor, institution_id, employee_id):
    from .selectors import current_assignments

    row = current_assignments(
        actor=actor, institution_id=institution_id, employee_id=employee_id
    ).first()
    if row is None:
        return None
    audit(row, actor, "read", {}, source="integration")
    return AssignmentIdentity(
        str(row.pk),
        str(row.employee_id),
        str(row.campus_id),
        str(row.department_id) if row.department_id else None,
        str(row.designation_id),
    )
