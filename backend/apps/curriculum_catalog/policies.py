from django.conf import settings
from django.db.models import Q
from .models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
)
from .integrations.upstream import grants

PATHS = {
    CourseCategory: "course-categories",
    CourseCatalog: "courses",
    CurriculumScheme: "schemes",
    CurriculumCourse: "curriculum-courses",
    CoursePrerequisite: "prerequisites",
}
OWNERS = {
    CourseCatalog: "owning_department",
    CurriculumScheme: "programme__department",
    CurriculumCourse: "curriculum_scheme__programme__department",
    CoursePrerequisite: "course__owning_department",
}


def enabled(actor):
    return bool(
        getattr(settings, "CURRICULUM_CATALOG_ENABLED", True)
        and actor
        and actor.is_authenticated
        and actor.is_active
    )


def permitted(actor, model, action):
    if not enabled(actor) or action == "delete":
        return False
    if actor.is_superuser:
        return True
    if model is CourseCategory and action != "view" and action != "export":
        return False
    return actor.has_perm(f"curriculum_catalog.{action}_{model._meta.model_name}")


def scoped(model, actor, action="view"):
    query = model.objects.all()
    if not permitted(actor, model, action):
        return query.none()
    if actor.is_superuser:
        return query
    rows = list(grants(actor))
    if model is CourseCategory:
        return query if rows else query.none()
    owner = OWNERS[model]
    visibility = Q(pk__in=[])
    for grant in rows:
        if action not in ("view", "export") and grant.role in ("TEACHER", "STUDENT"):
            continue
        part = Q(
            **{owner + "__campus__institution_id": grant.membership.institution_id}
        )
        if grant.campus_id:
            part &= Q(**{owner + "__campus_id": grant.campus_id})
        if grant.department_id:
            part &= Q(**{owner + "_id": grant.department_id})
        if not isinstance(grant.record_limits, dict):
            continue
        restrictions = [
            ("campuses", owner + "__campus_id__in"),
            ("departments", owner + "_id__in"),
            (
                PATHS[model],
                "course_id__in" if model is CoursePrerequisite else "pk__in",
            ),
        ]
        if model is CurriculumScheme:
            restrictions.append(("programmes", "programme_id__in"))
        if model is CurriculumCourse:
            restrictions += [
                ("schemes", "curriculum_scheme_id__in"),
                ("programmes", "curriculum_scheme__programme_id__in"),
                ("courses", "course_id__in"),
            ]
        if model is CoursePrerequisite:
            restrictions += [
                ("courses", "course_id__in"),
                ("courses", "prerequisite_course_id__in"),
            ]
        for name, lookup in restrictions:
            ids = grant.record_limits.get(name)
            if ids is not None:
                if not isinstance(ids, list) or any(
                    type(value) is not int or value < 1 for value in ids
                ):
                    part &= Q(pk__in=[])
                else:
                    part &= Q(**{lookup: ids[:500]})
        if grant.role in ("TEACHER", "STUDENT"):
            part &= Q(
                **{owner + "__is_active": True, owner + "__campus__is_active": True}
            )
        visibility |= part
    query = query.filter(visibility)
    # Confidential drafts require design authority, not merely view permission.
    if model in (CurriculumScheme, CurriculumCourse):
        scheme_field = (
            "status" if model is CurriculumScheme else "curriculum_scheme__status"
        )
        if not actor.has_perm("curriculum_catalog.change_curriculumscheme") or not any(
            row.role not in ("TEACHER", "STUDENT") for row in rows
        ):
            query = query.exclude(**{scheme_field: "DRAFT"})
    if model is CoursePrerequisite:
        query = query.filter(
            prerequisite_course_id__in=scoped(CourseCatalog, actor).values("pk")
        )
    return query


def institution_id(obj):
    if isinstance(obj, CourseCategory):
        return None
    owner = obj
    for part in OWNERS[type(obj)].split("__"):
        owner = getattr(owner, part)
    return owner.campus.institution_id


def related(query):
    model = query.model
    if model is CourseCategory:
        return query
    paths = [OWNERS[model] + "__campus__institution__university"]
    if model is CourseCatalog:
        paths += ["course_category"]
    if model is CurriculumScheme:
        paths += ["specialization"]
    if model is CurriculumCourse:
        paths += [
            "course__owning_department__campus__institution",
            "course__course_category",
            "course_category",
            "semester",
        ]
    if model is CoursePrerequisite:
        paths += ["prerequisite_course__owning_department__campus__institution"]
    return query.select_related(*paths)
