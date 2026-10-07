from functools import wraps
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError
from uuid import uuid4
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from .models import CurriculumScheme, CurriculumCourse
from .policies import scoped
from .services import (
    Command,
    execute,
    version,
    StaleVersion,
    Conflict,
    FIELDS,
    snapshot,
    emit,
    bump,
    validate_mapping,
)


def stable_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except IntegrityError as error:
            if error.args and error.args[0] in (1062, 1451, 1452, 3819, 4025):
                raise Conflict(
                    "Duplicate values, invalid constraints or protected references."
                ) from None
            raise
        except ModelValidationError as error:
            raise ValidationError(
                getattr(error, "message_dict", {"non_field_errors": error.messages})
            ) from None

    return wrapped


def locked_scheme(pk, actor, action, expected_version):
    ContentType.objects.select_for_update().get(
        app_label="organization", model="university"
    )
    scheme = (
        scoped(CurriculumScheme, actor, action)
        .select_for_update()
        .filter(pk=pk)
        .first()
    )
    if scheme is None:
        raise NotFound()
    if expected_version != version(scheme):
        raise StaleVersion()
    return scheme


def clone_scheme(pk, *, actor, expected_version, values, reason):
    if not reason or len(reason) > 250:
        raise ValidationError({"reason": "A bounded reason is required."})
    if set(values) - {
        "scheme_code",
        "scheme_name",
        "effective_from",
        "effective_to",
        "regulation_year",
    }:
        raise ValidationError("Unsupported clone fields.")
    if not values.get("scheme_code"):
        raise ValidationError({"scheme_code": "A new code is required."})
    with transaction.atomic():
        ContentType.objects.select_for_update().get(
            app_label="organization", model="university"
        )
        actor = get_user_model().objects.get(pk=actor.pk)
        source = locked_scheme(pk, actor, "clone", expected_version)
        if source.composition.exclude(
            pk__in=scoped(CurriculumCourse, actor).values("pk")
        ).exists():
            raise PermissionDenied(
                "Complete composition read access is required to clone."
            )
        body = {name: getattr(source, name) for name in FIELDS[CurriculumScheme]}
        body.update(values)
        clone = execute(Command(CurriculumScheme, actor, body, reason=reason))
        correlation = str(uuid4())
        for row in source.composition.order_by("pk"):
            payload = {name: getattr(row, name) for name in FIELDS[CurriculumCourse]}
            payload["curriculum_scheme_id"] = clone.pk
            execute(
                Command(
                    CurriculumCourse,
                    actor,
                    payload,
                    reason=reason,
                    correlation_id=correlation,
                )
            )
        emit(clone, actor, "clone", {}, reason, correlation)
        return clone


def bulk_compose(pk, *, actor, expected_version, changes, reason=""):
    if not isinstance(changes, list) or not 1 <= len(changes) <= 100:
        raise ValidationError("Supply 1 to 100 changes.")
    with transaction.atomic():
        ContentType.objects.select_for_update().get(
            app_label="organization", model="university"
        )
        actor = get_user_model().objects.get(pk=actor.pk)
        scheme = locked_scheme(pk, actor, "change", expected_version)
        if scheme.status != "DRAFT":
            raise Conflict("Only draft schemes can be composed.")
        results = []
        correlation = str(uuid4())
        for index, change in enumerate(changes):
            if not isinstance(change, dict) or set(change) - {
                "id",
                "version",
                "values",
                "remove",
            }:
                raise ValidationError({"row": index, "message": "Invalid command."})
            if "remove" in change and type(change["remove"]) is not bool:
                raise ValidationError(
                    {"row": index, "message": "remove must be a boolean."}
                )
            if change.get("remove") and change.get("id") is None:
                raise ValidationError(
                    {"row": index, "message": "Removal requires an ID."}
                )
            record_id = change.get("id")
            values = dict(change.get("values", {}))
            if record_id is not None:
                if (
                    not scoped(CurriculumCourse, actor, "change")
                    .filter(pk=record_id, curriculum_scheme=scheme)
                    .exists()
                ):
                    raise NotFound()
            else:
                values["curriculum_scheme_id"] = scheme.pk
            if (
                "curriculum_scheme_id" in values
                and values["curriculum_scheme_id"] != scheme.pk
            ):
                raise ValidationError("Cross-scheme batch assignment is not allowed.")
            row = execute(
                Command(
                    CurriculumCourse,
                    actor,
                    values,
                    record_id,
                    "remove" if change.get("remove") else "save",
                    change.get("version"),
                    reason,
                    correlation,
                )
            )
            results.append(str(row.pk) if row else None)
        return {"record_ids": results, "version": version(scheme)}


@stable_errors
def reorder(pk, *, actor, expected_version, semester_id, record_ids, reason=""):
    if (
        not isinstance(record_ids, list)
        or not 1 <= len(record_ids) <= 100
        or len(set(record_ids)) != len(record_ids)
    ):
        raise ValidationError("Provide distinct row IDs (maximum 100).")
    with transaction.atomic():
        ContentType.objects.select_for_update().get(
            app_label="organization", model="university"
        )
        actor = get_user_model().objects.get(pk=actor.pk)
        scheme = locked_scheme(pk, actor, "change", expected_version)
        if scheme.status != "DRAFT":
            raise Conflict("Only draft schemes can be reordered.")
        all_rows = list(
            scheme.composition.filter(semester_id=semester_id).order_by("pk")
        )
        if {str(row.pk) for row in all_rows} != {str(pk) for pk in record_ids}:
            raise ValidationError("Supply every row in the semester exactly once.")
        allowed = set(
            scoped(CurriculumCourse, actor, "compose")
            .filter(pk__in=[row.pk for row in all_rows])
            .values_list("pk", flat=True)
        )
        if allowed != {row.pk for row in all_rows}:
            raise PermissionDenied()
        before = {row.pk: snapshot(row) for row in all_rows}
        # Temporary clearing is private to this atomic transaction; final values are
        # validated and audited against the captured original snapshots.
        scheme.composition.filter(semester_id=semester_id).update(display_order=None)
        positions = {str(pk): index + 1 for index, pk in enumerate(record_ids)}
        for row in all_rows:
            row.display_order = positions[str(row.pk)]
            row.full_clean()
            validate_mapping(row, actor, scheme=scheme)
            row.save(update_fields=["display_order"])
            if before[row.pk] != snapshot(row):
                emit(row, actor, "reorder", before[row.pk], reason, str(uuid4()))
        bump(scheme)
        return {"version": version(scheme)}
