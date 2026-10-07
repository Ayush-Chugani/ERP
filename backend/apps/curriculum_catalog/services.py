"""Atomic governed commands shared by HTTP, admin and internal callers."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from rest_framework.exceptions import (
    APIException,
    ValidationError,
    PermissionDenied,
    NotFound,
)
from .models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
    CurriculumAudit,
    CurriculumEvent,
    CurriculumRevision,
)
from .policies import PATHS, scoped, permitted, institution_id, related
from .integrations.upstream import lookup, semester_map

FIELDS = {
    CourseCategory: (
        "category_code",
        "category_name",
        "is_graded",
        "contributes_to_gpa",
    ),
    CourseCatalog: (
        "owning_department_id",
        "course_category_id",
        "course_code",
        "course_title",
        "short_title",
        "course_type",
        "lecture_hours",
        "tutorial_hours",
        "practical_hours",
        "self_study_hours",
        "credits",
        "effective_from",
        "effective_to",
    ),
    CurriculumScheme: (
        "programme_id",
        "specialization_id",
        "scheme_code",
        "scheme_name",
        "regulation_year",
        "total_credits",
        "effective_from",
        "effective_to",
    ),
    CurriculumCourse: (
        "curriculum_scheme_id",
        "semester_id",
        "course_id",
        "course_category_id",
        "is_mandatory",
        "elective_group_code",
        "display_order",
        "internal_max_marks",
        "external_max_marks",
        "passing_marks",
        "exam_duration_minutes",
    ),
    CoursePrerequisite: ("course_id", "prerequisite_course_id", "minimum_grade"),
}


class Conflict(APIException):
    status_code = 409
    default_code = "curriculum_conflict"
    default_detail = "The curriculum change conflicts with existing data."


class StaleVersion(Conflict):
    default_code = "stale_version"
    default_detail = "This record changed. Reload it before saving."


@dataclass(frozen=True)
class Command:
    model: type
    actor: Any
    values: Mapping[str, Any] = field(default_factory=dict)
    pk: Any = None
    action: str = "save"
    expected_version: str | None = None
    reason: str = ""
    correlation_id: str = ""


def key(pk):
    return ":".join(str(value) for value in pk) if isinstance(pk, tuple) else str(pk)


def version(obj):
    return str(
        CurriculumRevision.objects.filter(
            resource=PATHS[type(obj)], record_key=key(obj.pk)
        )
        .values_list("version", flat=True)
        .first()
        or 0
    )


def bump(obj):
    revision, _ = CurriculumRevision.objects.get_or_create(
        resource=PATHS[type(obj)], record_key=key(obj.pk), defaults={"version": 0}
    )
    revision.version += 1
    revision.save(update_fields=["version"])


def snapshot(obj):
    if obj is None:
        return {}
    values = {name: getattr(obj, name) for name in FIELDS[type(obj)]}
    values["id"] = key(obj.pk)
    for name in ("status", "is_active"):
        if hasattr(obj, name):
            values[name] = getattr(obj, name)
    return {
        name: (
            str(value)
            if isinstance(value, (Decimal, date))
            or name.endswith("_id")
            and value is not None
            else value[:250]
            if isinstance(value, str)
            else value
        )
        for name, value in values.items()
    }


def emit(obj, actor, action, before, reason, correlation):
    after = snapshot(obj)
    event = CurriculumAudit.objects.create(
        actor=actor,
        institution_id=institution_id(obj),
        resource=PATHS[type(obj)],
        record_key=key(obj.pk),
        action=action,
        before=before,
        after={} if action == "remove" else after,
        reason=reason,
        correlation_id=correlation or str(uuid4()),
    )
    CurriculumEvent.objects.create(
        id=uuid4(),
        audit=event,
        event_type=f"{PATHS[type(obj)]}.{action}.v1",
        payload={
            "resource": event.resource,
            "record_key": event.record_key,
            "institution_id": str(event.institution_id)
            if event.institution_id
            else None,
            "action": action,
            "correlation_id": event.correlation_id,
        },
    )
    bump(obj)


def parent(model, pk, actor):
    row = related(scoped(model, actor)).filter(pk=pk).first()
    if row is None:
        raise NotFound("Parent is unavailable in your scope.")
    return row


def used(obj, *, skip=()):
    return any(
        rel.related_model.objects.filter(**{rel.field.name: obj}).exists()
        for rel in obj._meta.related_objects
        if rel.related_model not in skip
    )


def credit_summary(rows):
    mandatory = Decimal("0")
    groups = {}
    errors = []
    for row in rows:
        if row.is_mandatory:
            mandatory += row.course.credits
        else:
            group = (row.semester_id, row.elective_group_code)
            groups.setdefault(group, set()).add(row.course.credits)
    total = mandatory
    for group, credits in groups.items():
        if len(credits) != 1:
            errors.append(
                {
                    "group": str(group),
                    "message": "Elective alternatives must have equal credits.",
                }
            )
        else:
            total += next(iter(credits))
    return total, errors


def readiness(scheme, actor):
    issues = []
    context = lookup("programmes", scheme.programme_id, actor=actor)
    if not context.active:
        issues.append(
            {"field": "programme_id", "message": "Programme ancestors must be active."}
        )
    if scheme.specialization_id:
        specialization = lookup(
            "specializations", scheme.specialization_id, actor=actor
        )
        if (
            not specialization.active
            or specialization.programme_id != scheme.programme_id
        ):
            issues.append(
                {
                    "field": "specialization_id",
                    "message": "Select an active owned specialization.",
                }
            )
    if scheme.composition.exclude(
        pk__in=scoped(CurriculumCourse, actor).values("pk")
    ).exists():
        raise PermissionDenied(
            "Complete composition read access is required for validation."
        )
    rows = list(
        scheme.composition.select_related(
            "course__owning_department__campus",
            "course__course_category",
            "course_category",
            "semester",
        )
    )
    if not rows:
        issues.append(
            {"field": "composition", "message": "At least one course is required."}
        )
    semesters = semester_map(actor=actor, institution_id=context.institution_id)
    for row in rows:
        try:
            validate_mapping(
                row, actor, scheme=scheme, semester_values=semesters, activating=True
            )
        except (ValidationError, Conflict, PermissionDenied, NotFound) as error:
            issues.append({"record_id": str(row.pk), "message": str(error.detail)})
    total, group_errors = credit_summary(rows)
    issues += group_errors
    if scheme.total_credits is not None and total != scheme.total_credits:
        issues.append(
            {
                "field": "total_credits",
                "message": f"Declared target does not equal selected credits ({total}).",
            }
        )
    overlaps = CurriculumScheme.objects.filter(
        programme_id=scheme.programme_id,
        specialization_id=scheme.specialization_id,
        status="ACTIVE",
    ).exclude(pk=scheme.pk)
    if scheme.effective_to:
        overlaps = overlaps.filter(effective_from__lte=scheme.effective_to)
    overlaps = overlaps.filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=scheme.effective_from)
    )
    if overlaps.exists():
        issues.append(
            {
                "field": "effective_from",
                "message": "Another active scheme overlaps this interval.",
            }
        )
    return {
        "ready": not issues,
        "issues": issues,
        "selected_credits": str(total),
        "elective_selection": "one_per_semester_group",
    }


def validate_mapping(
    obj, actor, *, scheme=None, semester_values=None, activating=False
):
    scheme = scheme or parent(CurriculumScheme, obj.curriculum_scheme_id, actor)
    if not activating and scheme.status != "DRAFT":
        raise Conflict("Only draft schemes can be composed.")
    context = lookup(
        "programmes", scheme.programme_id, actor=actor, write=not activating
    )
    semesters = (
        semester_values
        if semester_values is not None
        else semester_map(actor=actor, institution_id=context.institution_id)
    )
    if (
        obj.semester_id not in semesters
        or not 1 <= semesters[obj.semester_id][0] <= context.duration_semesters
    ):
        raise ValidationError(
            {"semester_id": "Semester must be within the programme duration."}
        )
    course = parent(CourseCatalog, obj.course_id, actor)
    if not lookup("departments", course.owning_department_id, actor=actor).active:
        raise Conflict("Course department ancestors are inactive.")
    if institution_id(course) != context.institution_id:
        raise ValidationError(
            {"course_id": "Course must belong to the same institution."}
        )
    if not course.is_active or not course.course_category.is_active:
        raise ValidationError({"course_id": "Select an active course and category."})
    if course.course_category_id != obj.course_category_id:
        raise ValidationError(
            {"course_category_id": "Category must match the course default."}
        )
    if (
        course.effective_from
        and course.effective_from > scheme.effective_from
        or course.effective_to
        and (scheme.effective_to is None or course.effective_to < scheme.effective_to)
    ):
        raise ValidationError(
            {"course_id": "Course validity must cover the scheme interval."}
        )
    total = obj.internal_max_marks + obj.external_max_marks
    if not course.course_category.is_graded and (
        total != 0 or obj.passing_marks not in (None, Decimal(0))
    ):
        raise ValidationError(
            {
                "internal_max_marks": "Ungraded courses use zero marks and null/zero passing marks."
            }
        )
    if activating and course.course_category.is_graded and total <= 0:
        raise ValidationError(
            {
                "internal_max_marks": "Graded courses require positive total marks before activation."
            }
        )
    if obj.exam_duration_minutes is not None and (
        obj.exam_duration_minutes <= 0 or obj.external_max_marks <= 0
    ):
        raise ValidationError(
            {
                "exam_duration_minutes": "A positive duration requires external examination marks."
            }
        )
    if obj.display_order is not None and obj.display_order <= 0:
        raise ValidationError({"display_order": "Use a positive order or null."})


def graph_edges(institution):
    rows = list(
        CoursePrerequisite.objects.filter(
            course__owning_department__campus__institution_id=institution
        ).values_list("course_id", "prerequisite_course_id")[:5001]
    )
    if len(rows) > 5000:
        raise Conflict("Graph exceeds the supported 5000-edge validation limit.")
    return rows


def cycle_path(edges):
    graph = {}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
    done = set()
    for start in graph:
        if start in done:
            continue
        stack = [(start, iter(graph.get(start, ())))]
        path = [start]
        active = {start: 0}
        while stack:
            node, children = stack[-1]
            target = next(children, None)
            if target is None:
                stack.pop()
                path.pop()
                active.pop(node, None)
                done.add(node)
            elif target in active:
                return path[active[target] :] + [target]
            elif target not in done:
                active[target] = len(path)
                path.append(target)
                stack.append((target, iter(graph.get(target, ()))))
    return None


def impact(obj, actor):
    # No hidden record IDs/counts in cross-scope relation reports.
    counts = {}
    for relation in obj._meta.related_objects:
        if relation.related_model in FIELDS:
            counts[PATHS[relation.related_model]] = (
                scoped(relation.related_model, actor)
                .filter(**{relation.field.name: obj})
                .count()
            )
    return {
        "visible_references": counts,
        "has_protected_references": used(obj),
        "hard_delete_allowed": False,
    }


def execute(command: Command):
    model = command.model
    values = dict(command.values)
    if model not in FIELDS or set(values) - set(FIELDS[model]):
        raise ValidationError({"non_field_errors": ["Unknown or protected fields."]})
    if not isinstance(command.reason, str) or len(command.reason) > 250:
        raise ValidationError({"reason": "Use at most 250 characters."})
    if not isinstance(command.correlation_id, str) or len(command.correlation_id) > 64:
        raise ValidationError({"correlation_id": "Invalid correlation ID."})
    try:
        with transaction.atomic():
            ContentType.objects.select_for_update().get(
                app_label="organization", model="university"
            )
            actor = get_user_model().objects.get(pk=command.actor.pk)
            permission = (
                ("change" if command.pk is not None else "add")
                if command.action == "save"
                else command.action
            )
            if model is CoursePrerequisite:
                permission = "manage" if command.action != "view" else "view"
            if command.action == "remove" and model is CurriculumCourse:
                permission = "compose"
            if command.pk is not None:
                obj = (
                    related(scoped(model, actor, permission))
                    .select_for_update()
                    .filter(pk=command.pk)
                    .first()
                )
                if obj is None:
                    raise NotFound()
                if (
                    command.expected_version is None
                    or command.expected_version != version(obj)
                ):
                    raise StaleVersion()
            else:
                if command.action != "save" or not permitted(actor, model, permission):
                    raise PermissionDenied()
                obj = model()
            before = snapshot(obj) if command.pk is not None else {}
            if command.action == "save":
                if isinstance(obj, CurriculumScheme) and obj.status != "DRAFT":
                    raise Conflict(
                        "Active and retired schemes are immutable; clone instead."
                    )
                immutable = {
                    "owning_department_id",
                    "programme_id",
                    "curriculum_scheme_id",
                }
                if model is CoursePrerequisite:
                    immutable |= {"course_id", "prerequisite_course_id"}
                if command.pk is not None:
                    for name in immutable & values.keys():
                        if values[name] != getattr(obj, name):
                            raise Conflict("Ownership/identity is immutable.")
                    if (
                        model is CourseCategory
                        and used(obj)
                        and any(
                            name in values and values[name] != getattr(obj, name)
                            for name in ("is_graded", "contributes_to_gpa")
                        )
                    ):
                        raise Conflict("Referenced category semantics cannot change.")
                    if (
                        model is CourseCatalog
                        and used(obj)
                        and any(
                            name in values and values[name] != getattr(obj, name)
                            for name in FIELDS[model]
                            if name not in ("course_title", "short_title")
                        )
                    ):
                        raise Conflict(
                            "Referenced course semantics are immutable; create a new code."
                        )
                for name, value in values.items():
                    if (
                        name.endswith("_id")
                        and value is not None
                        and (type(value) is not int or value <= 0)
                    ):
                        raise ValidationError({name: "Use a positive integer ID."})
                    if name.startswith("is_") or name == "contributes_to_gpa":
                        if type(value) is not bool:
                            raise ValidationError({name: "Use a boolean."})
                    setattr(obj, name, value)
            elif command.action in ("activate", "deactivate") and model in (
                CourseCategory,
                CourseCatalog,
            ):
                if values:
                    raise ValidationError("Lifecycle payload cannot edit fields.")
                if not command.reason.strip():
                    raise ValidationError({"reason": "A reason is required."})
                target = command.action == "activate"
                if obj.is_active == target:
                    return obj
                obj.is_active = target
            elif model is CurriculumScheme and command.action in ("activate", "retire"):
                if values:
                    raise ValidationError("Lifecycle payload cannot edit fields.")
                if not command.reason.strip():
                    raise ValidationError({"reason": "A reason is required."})
                target = "ACTIVE" if command.action == "activate" else "RETIRED"
                if obj.status == target:
                    return obj
                if (
                    obj.status == "RETIRED"
                    or command.action == "activate"
                    and obj.status != "DRAFT"
                ):
                    raise Conflict("Invalid scheme transition.")
                if command.action == "activate":
                    report = readiness(obj, actor)
                    if not report["ready"]:
                        raise Conflict(report)
                elif used(obj, skip=(CurriculumCourse,)):
                    raise Conflict(
                        "Downstream dependents prevent retirement without integration review."
                    )
                obj.status = target
            elif command.action == "remove" and model in (
                CurriculumCourse,
                CoursePrerequisite,
            ):
                if values or not command.reason.strip():
                    raise ValidationError({"reason": "Removal requires only a reason."})
                if model is CurriculumCourse:
                    scheme = parent(CurriculumScheme, obj.curriculum_scheme_id, actor)
                    if scheme.status != "DRAFT":
                        raise Conflict("Only draft composition can be removed.")
                    if (
                        not scoped(CurriculumScheme, actor, "change")
                        .filter(pk=scheme.pk)
                        .exists()
                    ):
                        raise PermissionDenied()
                else:
                    if (
                        not scoped(CourseCatalog, actor, "change")
                        .filter(pk=obj.course_id)
                        .exists()
                    ):
                        raise PermissionDenied()
                    if obj.course.curriculum_mappings.exclude(
                        curriculum_scheme__status="DRAFT"
                    ).exists():
                        raise Conflict(
                            "Prerequisites used in active/history schemes are immutable."
                        )
                if used(obj):
                    raise Conflict("Protected references prevent removal.")
                emit(
                    obj, actor, "remove", before, command.reason, command.correlation_id
                )
                if model is CurriculumCourse:
                    bump(scheme)
                obj.delete()
                return None
            else:
                raise ValidationError("Unsupported command.")
            # Resolve and authorize relations before model clean queries them.
            if model is CourseCatalog:
                context = lookup(
                    "departments", obj.owning_department_id, actor=actor, write=True
                )
                category = parent(CourseCategory, obj.course_category_id, actor)
                if (command.pk is None or command.action == "activate") and (
                    not context.active or not category.is_active
                ):
                    raise Conflict("New assignments require active parents.")
            if model is CurriculumScheme:
                context = lookup(
                    "programmes", obj.programme_id, actor=actor, write=True
                )
                if not context.active:
                    raise Conflict("Programme ancestors are inactive.")
                if obj.specialization_id:
                    special = lookup(
                        "specializations",
                        obj.specialization_id,
                        actor=actor,
                        write=True,
                    )
                    if special.programme_id != obj.programme_id or not special.active:
                        raise ValidationError(
                            {
                                "specialization_id": "Select an active specialization of this programme."
                            }
                        )
            if model is CurriculumCourse:
                scheme = parent(CurriculumScheme, obj.curriculum_scheme_id, actor)
                if (
                    not scoped(CurriculumScheme, actor, "change")
                    .filter(pk=scheme.pk)
                    .exists()
                ):
                    raise PermissionDenied()
                parent(CourseCatalog, obj.course_id, actor)
                parent(CourseCategory, obj.course_category_id, actor)
            if model is CoursePrerequisite:
                course = parent(CourseCatalog, obj.course_id, actor)
                required = parent(CourseCatalog, obj.prerequisite_course_id, actor)
                if (
                    not scoped(CourseCatalog, actor, "change")
                    .filter(pk=course.pk)
                    .exists()
                ):
                    raise PermissionDenied()
                if institution_id(course) != institution_id(required):
                    raise ValidationError(
                        {
                            "prerequisite_course_id": "Cross-institution prerequisites are not permitted."
                        }
                    )
                if not course.is_active or not required.is_active:
                    raise Conflict("Prerequisite endpoints must be active.")
                if course.curriculum_mappings.exclude(
                    curriculum_scheme__status="DRAFT"
                ).exists():
                    raise Conflict(
                        "Prerequisites used in active/history schemes are immutable."
                    )
                if (
                    course.effective_to
                    and required.effective_from
                    and required.effective_from > course.effective_to
                ):
                    raise Conflict(
                        "Prerequisite starts after the course validity ends."
                    )
            obj.full_clean()
            if model is CurriculumCourse:
                validate_mapping(obj, actor, scheme=scheme)
            if model is CoursePrerequisite:
                if (
                    obj.minimum_grade
                    and obj.minimum_grade not in settings.CURRICULUM_GRADE_CODES
                ):
                    raise ValidationError(
                        {
                            "minimum_grade": "Use a configured grade code, or leave empty."
                        }
                    )
                edges = graph_edges(institution_id(course))
                if command.pk is None:
                    edges.append((obj.course_id, obj.prerequisite_course_id))
                cycle = cycle_path(edges)
                if cycle:
                    visible = set(
                        scoped(CourseCatalog, actor)
                        .filter(pk__in=cycle)
                        .values_list("pk", flat=True)
                    )
                    raise Conflict(
                        {
                            "cycle_path": cycle
                            if all(pk in visible for pk in cycle)
                            else [],
                            "message": "Prerequisite cycle detected.",
                        }
                    )
            obj.save()
            if not scoped(model, actor, permission).filter(pk=obj.pk).exists():
                raise PermissionDenied("Record limits do not allow this record.")
            if model is CurriculumCourse:
                _, errors = credit_summary(
                    list(scheme.composition.select_related("course"))
                )
                if errors:
                    raise ValidationError({"elective_group_code": errors})
                bump(scheme)
            if before != snapshot(obj):
                emit(
                    obj,
                    actor,
                    command.action
                    if command.action != "save"
                    else ("update" if before else "create"),
                    before,
                    command.reason,
                    command.correlation_id,
                )
            return obj
    except IntegrityError as error:
        if error.args and error.args[0] in (1062, 1451, 1452, 3819, 4025):
            raise Conflict(
                "Duplicate values, invalid constraints or protected references."
            ) from None
        raise
    except ModelValidationError as error:
        if any(
            item.code in ("unique", "unique_together")
            for group in getattr(error, "error_dict", {}).values()
            for item in group
        ):
            raise Conflict("A record with these values already exists.") from None
        raise ValidationError(
            getattr(error, "message_dict", {"non_field_errors": error.messages})
        ) from None


def save(model, values, *, actor, pk=None, expected_version=None):
    return execute(Command(model, actor, values, pk, expected_version=expected_version))
