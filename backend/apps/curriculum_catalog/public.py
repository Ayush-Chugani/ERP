"""Immutable contracts for future consumers; no unrestricted manager exported."""

from dataclasses import dataclass
from . import selectors
from .models import CourseCatalog, CurriculumScheme, CurriculumEvent, CurriculumAudit
from .policies import scoped, related, permitted
from .integrations.upstream import grants
from rest_framework.exceptions import PermissionDenied


@dataclass(frozen=True)
class CourseInfo:
    id: str
    code: str
    title: str
    credits: str
    active: bool


@dataclass(frozen=True)
class SchemeInfo:
    id: str
    code: str
    programme_id: str
    specialization_id: str | None


@dataclass(frozen=True)
class MappingInfo:
    id: str
    course_id: str
    semester_id: str
    credits: str
    mandatory: bool
    elective_group: str | None
    internal_marks: str
    external_marks: str
    passing_marks: str | None


def course(*, actor, institution_id, course_id):
    selectors.context(actor, institution_id)
    row = (
        scoped(CourseCatalog, actor)
        .filter(pk=course_id, owning_department__campus__institution_id=institution_id)
        .first()
    )
    return (
        CourseInfo(
            str(row.pk),
            row.course_code,
            row.course_title,
            str(row.credits),
            row.is_active,
        )
        if row
        else None
    )


def current_scheme(**kwargs):
    row = selectors.current_scheme(**kwargs)
    return (
        SchemeInfo(
            str(row.pk),
            row.scheme_code,
            str(row.programme_id),
            str(row.specialization_id) if row.specialization_id else None,
        )
        if row
        else None
    )


def semester_curriculum(**kwargs):
    return tuple(
        MappingInfo(
            str(row.pk),
            str(row.course_id),
            str(row.semester_id),
            str(row.course.credits),
            row.is_mandatory,
            row.elective_group_code,
            str(row.internal_max_marks),
            str(row.external_max_marks),
            str(row.passing_marks) if row.passing_marks is not None else None,
        )
        for row in selectors.semester_curriculum(**kwargs)
    )


def prerequisite_graph(**kwargs):
    values = selectors.graph(**kwargs)
    return tuple(str(pk) for pk in values["order"]), tuple(
        (str(a), str(b)) for a, b in values["edges"]
    )


def dependency_impact(*, actor, institution_id, course_id):
    values = selectors.graph(actor=actor, institution_id=institution_id)
    dependents = {}
    for source, target in values["edges"]:
        dependents.setdefault(target, []).append(source)
    pending = [course_id]
    seen = set()
    while pending:
        pk = pending.pop()
        for child in dependents.get(pk, []):
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return tuple(str(pk) for pk in sorted(seen))


def events(*, actor, institution_id, after_audit_id=0, limit=100):
    """Scoped polling contract. Consumers persist their cursor and deduplicate event UUIDs."""
    selectors.context(actor, institution_id)
    if not actor.is_superuser:
        raise PermissionDenied(
            "Platform event consumption requires a support principal."
        )
    rows = CurriculumEvent.objects.filter(
        audit__institution_id=institution_id, audit_id__gt=after_audit_id
    ).order_by("audit_id")[: min(max(limit, 1), 100)]
    return tuple(
        {
            "id": str(row.pk),
            "cursor": str(row.audit_id),
            "type": row.event_type,
            "schema_version": row.schema_version,
            "payload": row.payload,
        }
        for row in rows
    )


def credit_totals(*, actor, institution_id, scheme_id):
    selectors.context(actor, institution_id)
    scheme = (
        scoped(CurriculumScheme, actor)
        .filter(
            pk=scheme_id, programme__department__campus__institution_id=institution_id
        )
        .first()
    )
    if scheme is None:
        return None
    from .models import CurriculumCourse
    from .services import credit_summary

    if scheme.composition.exclude(
        pk__in=scoped(CurriculumCourse, actor).values("pk")
    ).exists():
        raise PermissionDenied("Complete composition scope is required.")
    total, issues = credit_summary(list(scheme.composition.select_related("course")))
    return {
        "selected_credits": str(total),
        "declared_credits": str(scheme.total_credits)
        if scheme.total_credits is not None
        else None,
        "issues": tuple(str(issue) for issue in issues),
    }


def elective_groups(*, actor, institution_id, scheme_id, semester_id):
    rows = semester_curriculum(
        actor=actor,
        institution_id=institution_id,
        scheme_id=scheme_id,
        semester_id=semester_id,
    )
    result = {}
    for row in rows:
        if not row.mandatory:
            result.setdefault(row.elective_group, []).append(row)
    return tuple((name, 1, tuple(items)) for name, items in sorted(result.items()))


def eligibility_inputs(*, actor, institution_id, course_id):
    info = course(actor=actor, institution_id=institution_id, course_id=course_id)
    if info is None:
        return None
    from .models import CoursePrerequisite

    edges = (
        scoped(CoursePrerequisite, actor)
        .filter(course_id=course_id)
        .order_by("prerequisite_course_id")
    )
    if (
        CoursePrerequisite.objects.filter(course_id=course_id)
        .exclude(pk__in=edges.values("pk"))
        .exists()
    ):
        raise PermissionDenied("Complete prerequisite scope is required.")
    return {
        "course": info,
        "prerequisites": tuple(
            (str(row.prerequisite_course_id), row.minimum_grade) for row in edges
        ),
    }
