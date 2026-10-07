from datetime import date
from dataclasses import dataclass
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from .models import (
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
    CurriculumEvent,
)
from .policies import scoped, related, enabled
from .integrations.upstream import grants, lookup
from .services import Conflict, credit_summary, cycle_path


def context(actor, institution_id):
    if type(institution_id) is not int or institution_id <= 0 or not enabled(actor):
        raise PermissionDenied()
    if (
        not actor.is_superuser
        and not grants(actor).filter(membership__institution_id=institution_id).exists()
    ):
        raise PermissionDenied()


def current_scheme(
    *, actor, institution_id, programme_id, specialization_id, on_date: date
):
    context(actor, institution_id)
    owner = lookup("programmes", programme_id, actor=actor)
    if owner.institution_id != institution_id:
        raise PermissionDenied()
    rows = list(
        related(scoped(CurriculumScheme, actor))
        .filter(
            programme_id=programme_id,
            specialization_id=specialization_id,
            status="ACTIVE",
            effective_from__lte=on_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))[:2]
    )
    if len(rows) > 1:
        raise Conflict("Multiple active schemes; reconciliation is required.")
    return rows[0] if rows else None


def semester_curriculum(*, actor, institution_id, scheme_id, semester_id):
    context(actor, institution_id)
    return related(scoped(CurriculumCourse, actor)).filter(
        curriculum_scheme_id=scheme_id,
        semester_id=semester_id,
        curriculum_scheme__programme__department__campus__institution_id=institution_id,
    )


def graph(*, actor, institution_id):
    context(actor, institution_id)
    courses = list(
        scoped(CourseCatalog, actor)
        .filter(owning_department__campus__institution_id=institution_id)
        .values_list("pk", flat=True)[:5001]
    )
    if len(courses) > 5000:
        raise Conflict("Graph exceeds 5000 nodes.")
    edges = list(
        scoped(CoursePrerequisite, actor)
        .filter(course_id__in=courses, prerequisite_course_id__in=courses)
        .values_list("course_id", "prerequisite_course_id")[:5001]
    )
    if len(edges) > 5000:
        raise Conflict("Graph exceeds 5000 edges.")
    cycle = cycle_path(edges)
    if cycle:
        raise Conflict({"cycle_path": cycle})
    # Kahn ordering with prerequisite -> dependent direction, O(V+E).
    from collections import deque

    indegree = {pk: 0 for pk in courses}
    dependents = {pk: [] for pk in courses}
    for course, required in edges:
        indegree[course] += 1
        dependents[required].append(course)
    ready = deque(pk for pk in courses if indegree[pk] == 0)
    ordered = []
    while ready:
        pk = ready.popleft()
        ordered.append(pk)
        for target in dependents[pk]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return {"order": ordered, "edges": edges}
