"""Minimal reference catalogues and scoped contribution queries."""

from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.conferences.models import ConferenceEvent
from apps.curriculum_catalog.models import CourseCatalog
from apps.organization.models import Programme
from apps.people_master.models import Student
from apps.people_master.permissions import scoped as people_scope
from apps.research_publications.models import Journal
from apps.staff_profile.models import ExternalOrganization

from .permissions import activity_scope

REFERENCES = {
    "organization": (ExternalOrganization, "organization_name"),
    "journal": (Journal, "journal_name"),
    "conference_event": (ConferenceEvent, "conference_title"),
    "programme": (Programme, "programme_name"),
    "course": (CourseCatalog, "course_title"),
    "student": (Student, "display_name"),
}


def reference_rows(actor, name, institution_id=None):
    model, _ = REFERENCES[name]
    rows = model.objects.all()
    if name == "student":
        paths = {
            "INSTITUTION": "institution_id",
            "CAMPUS": "campus_id",
            "DEPARTMENT": "department_id",
            "SELF": "accountlink__user_id",
        }
        rows = (
            people_scope(Student, actor)
            .filter(student_status="ACTIVE")
            .filter(activity_scope(actor, paths=paths))
        )
        if institution_id:
            rows = rows.filter(institution_id=institution_id)
        return rows
    rows = rows.filter(is_active=True)
    prefix = {"programme": "department__", "course": "owning_department__"}.get(name)
    if prefix:
        paths = {
            "INSTITUTION": prefix + "campus__institution_id",
            "CAMPUS": prefix + "campus_id",
            "DEPARTMENT": prefix + "pk",
        }
        # SELF allows academic context within the employee's current/dated assignment scope.
        from apps.people_master.models import EmployeeAssignment

        own = EmployeeAssignment.objects.filter(employee__accountlink__user=actor)
        own_allowed = own.filter(
            activity_scope(
                actor,
                "CREATE",
                paths={
                    "INSTITUTION": "employee__institution_id",
                    "CAMPUS": "campus_id",
                    "DEPARTMENT": "department_id",
                    "SELF": "employee__accountlink__user_id",
                },
            )
        )
        own_allowed = own_allowed.filter(
            activity_scope(
                actor,
                paths={
                    "INSTITUTION": "employee__institution_id",
                    "CAMPUS": "campus_id",
                    "DEPARTMENT": "department_id",
                    "SELF": "employee__accountlink__user_id",
                },
            )
        )
        scope = activity_scope(actor, paths=paths)
        scope |= Q(**{prefix + "pk__in": own_allowed.values("department_id")})
        rows = rows.filter(scope)
        if institution_id:
            rows = rows.filter(**{prefix + "campus__institution_id": institution_id})
    return rows


def validate_references(actor, row):
    for name in REFERENCES:
        pk = getattr(row, name + "_id")
        if (
            pk is not None
            and not reference_rows(actor, name, row.staff_activity.institution_id)
            .filter(pk=pk)
            .exists()
        ):
            raise ValidationError(
                {
                    name
                    + "_id": "Select an active reference within your authorized scope and institution."
                }
            )


def context_summary(row):
    # All relations are selected by the list/detail query; expose no student profile.
    return [
        {
            "kind": name,
            "id": str(getattr(row, name + "_id")),
            "label": getattr(getattr(row, name), label),
        }
        for name, (_, label) in REFERENCES.items()
        if getattr(row, name + "_id")
    ]


def duplicate_candidates(actor, row):
    from .models import StaffProfessionalContribution

    rows = StaffProfessionalContribution.objects.filter(
        activity_scope(actor),
        student_read_scope(actor),
        staff_activity__deleted_at__isnull=True,
        staff_activity__employee_id=row.staff_activity.employee_id,
        professional_contribution_type_id=row.professional_contribution_type_id,
        title_topic=row.title_topic,
        contribution_date=row.contribution_date,
        appointment_reference_number=row.appointment_reference_number,
    )
    for name in REFERENCES:
        rows = rows.filter(**{name + "_id": getattr(row, name + "_id")})
    if row.pk:
        rows = rows.exclude(pk=row.pk)
    return list(rows.order_by("-pk").values_list("pk", flat=True)[:5])


def student_read_scope(actor):
    return Q(student__isnull=True) | Q(
        student_id__in=people_scope(Student, actor).values("pk")
    )
