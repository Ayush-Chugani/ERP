from dataclasses import dataclass, field
from datetime import timedelta
from functools import wraps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError, models
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from . import models as m
from .catalogue import FIELDS, PATHS, SHARED, RESTRICTED, CONFIDENTIAL
from .permissions import enabled, permitted, scoped, owner, institution_id, related
from .integrations.upstream import context
from .exceptions import PeopleConflict, StalePeopleVersion
from .context import request_id
from uuid import uuid4


@dataclass(frozen=True)
class Command:
    model: type
    actor: object
    values: dict = field(default_factory=dict)
    pk: object = None
    action: str = "save"
    expected_version: str | None = None
    reason: str = ""
    source: str = "api"


def key(pk):
    return ":".join(map(str, pk)) if isinstance(pk, tuple) else str(pk)


def version(obj):
    return str(
        m.PeopleRevision.objects.filter(
            resource=PATHS[type(obj)], record_key=key(obj.pk)
        )
        .values_list("version", flat=True)
        .first()
        or 0
    )


def snapshot(obj):
    # Retain changes without copying sensitive field values into audit storage.
    return {
        f.attname: (
            "[redacted]"
            if f.attname in RESTRICTED | CONFIDENTIAL
            or isinstance(f, (models.CharField, models.TextField))
            and f.name not in ("student_status", "employment_status")
            else str(getattr(obj, f.attname))
            if getattr(obj, f.attname) is not None
            else None
        )
        for f in obj._meta.fields
        if not isinstance(f, (models.GeneratedField, models.CompositePrimaryKey))
    }


def audit(obj, actor, action, before, reason="", source="api", changed_fields=()):
    event = m.PeopleAudit.objects.create(
        correlation_id=request_id.get() or uuid4(),
        actor=actor,
        institution_id=institution_id(obj),
        resource=PATHS[type(obj)],
        record_key=key(obj.pk),
        action=action,
        before=before,
        after={**snapshot(obj), "_changed_fields": list(changed_fields)},
        reason=reason,
        source=source,
    )
    if action != "read":
        m.PeopleEvent.objects.create(
            audit=event,
            event_type=f"people.{PATHS[type(obj)]}.{action}.v1",
            payload={
                "record_key": key(obj.pk),
                "institution_id": str(institution_id(obj))
                if institution_id(obj)
                else None,
                "action": action,
            },
        )
        revision, _ = m.PeopleRevision.objects.get_or_create(
            resource=PATHS[type(obj)], record_key=key(obj.pk)
        )
        revision.version += 1
        revision.save(update_fields=["version"])


def stable_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except IntegrityError as error:
            if error.args and error.args[0] in (1062, 1451, 1452, 3819, 4025):
                raise PeopleConflict(
                    "Duplicate values, invalid constraints or protected references."
                ) from None
            raise
        except DjangoValidationError as error:
            raise ValidationError(
                getattr(error, "message_dict", {"non_field_errors": error.messages})
            ) from None

    return wrapped


def lock_actor(actor):
    ContentType.objects.select_for_update().get(
        app_label="organization", model="university"
    )
    actor = get_user_model().objects.get(pk=actor.pk)
    if not enabled(actor):
        raise PermissionDenied()
    return actor


def parent_checks(obj, actor, old):
    for f in obj._meta.fields:
        if not isinstance(f, models.ForeignKey) or getattr(obj, f.attname) is None:
            continue
        value = getattr(obj, f.attname)
        if f.related_model._meta.app_label == "people_master":
            found = related(scoped(f.related_model, actor)).filter(pk=value).first()
        elif f.related_model._meta.app_label == "curriculum_catalog":
            from apps.curriculum_catalog.public import course

            found = course(
                actor=actor, institution_id=institution_id(obj), course_id=value
            )
        else:
            found = f.related_model.objects.filter(pk=value).first()
        if found is None:
            raise NotFound("Parent unavailable.")
        if (old.get(f.attname) != value) and not getattr(
            found, "is_active", getattr(found, "active", True)
        ):
            raise ValidationError({f.attname: "Select an active parent."})
    root = owner(obj)
    if type(obj) not in SHARED:
        if isinstance(root, m.Student):
            context(
                actor,
                root.institution_id,
                root.campus_id,
                root.department_id,
                write=True,
            )
        elif isinstance(root, m.Employee):
            primary = (
                m.EmployeeAssignment.objects.filter(
                    employee=root, is_primary=True, end_date__isnull=True
                ).first()
                if root.pk
                else None
            )
            context(
                actor,
                root.institution_id,
                primary.campus_id if primary else None,
                primary.department_id if primary else None,
                write=True,
            )
        else:
            context(actor, root.institution_id, write=True)
    for child, parent in [
        ("state", "country"),
        ("sub_caste", "caste"),
        ("caste", "social_category"),
    ]:
        child_id = getattr(obj, child + "_id", None)
        if child_id:
            child_obj = getattr(obj, child)
            if getattr(child_obj, parent + "_id") != getattr(obj, parent + "_id", None):
                raise ValidationError(
                    {child + "_id": "Parent selection does not match."}
                )
    if isinstance(obj, m.Employee):
        external = obj.employment_source.is_external
        if external != bool(obj.external_agency_id):
            raise ValidationError(
                {
                    "external_agency_id": "External employment requires an agency; internal employment must not have one."
                }
            )
        if not external and obj.agency_employee_number:
            raise ValidationError(
                {
                    "agency_employee_number": "Only external employment has an agency number."
                }
            )
        if obj.external_agency_id:
            agency = obj.external_agency
            if agency.institution_id != obj.institution_id:
                raise ValidationError(
                    {
                        "external_agency_id": "Agency must belong to the employee institution."
                    }
                )
            if (
                agency.contract_start_date
                and obj.joining_date < agency.contract_start_date
                or agency.contract_end_date
                and obj.joining_date > agency.contract_end_date
            ):
                raise ValidationError(
                    {
                        "joining_date": "Joining date must fall within the agency contract."
                    }
                )
    if isinstance(obj, m.EmployeeAssignment):
        if obj.campus.institution_id != obj.employee.institution_id:
            raise ValidationError(
                {"campus_id": "Campus belongs to another institution."}
            )
        if obj.department_id and obj.department.campus_id != obj.campus_id:
            raise ValidationError(
                {"department_id": "Department must belong to campus."}
            )
        context(
            actor,
            obj.employee.institution_id,
            obj.campus_id,
            obj.department_id,
            write=True,
        )
        if obj.start_date < obj.employee.joining_date:
            raise ValidationError({"start_date": "Assignment cannot precede joining."})
    if isinstance(obj, m.StudentResidence) and obj.is_current and obj.end_date:
        raise ValidationError({"is_current": "An ended residence cannot be current."})


def check_primary_overlap(obj):
    if (
        type(obj) not in (m.StudentAddress, m.EmployeeAddress, m.EmployeeAssignment)
        or not obj.is_primary
    ):
        return
    from datetime import date

    start, end = (
        ("start_date", "end_date")
        if isinstance(obj, m.EmployeeAssignment)
        else ("valid_from", "valid_to")
    )
    owner_field = "student_id" if isinstance(obj, m.StudentAddress) else "employee_id"
    left = getattr(obj, start) or date.min
    right = getattr(obj, end) or date.max
    conflicts = (
        type(obj)
        .objects.filter(**{owner_field: getattr(obj, owner_field), "is_primary": True})
        .exclude(pk=obj.pk)
        .filter(
            models.Q(**{end + "__isnull": True}) | models.Q(**{end + "__gte": left})
        )
        .filter(
            models.Q(**{start + "__isnull": True})
            | models.Q(**{start + "__lte": right})
        )
    )
    if conflicts.exists():
        raise PeopleConflict("Primary effective periods must not overlap.")


def activation_ready(root):
    today = timezone.localdate()
    model = m.StudentAddress if isinstance(root, m.Student) else m.EmployeeAddress
    name = "student" if isinstance(root, m.Student) else "employee"
    addresses = model.objects.filter(
        **{name: root, "is_primary": True, "valid_to__isnull": True}
    ).filter(models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=today))
    if not addresses.exists():
        raise PeopleConflict("Activation requires a current primary address.")
    if (
        isinstance(root, m.Employee)
        and not m.EmployeeAssignment.objects.filter(
            employee=root, is_primary=True, end_date__isnull=True, start_date__lte=today
        ).exists()
    ):
        raise PeopleConflict("Activation requires a current primary assignment.")


@stable_errors
def execute(command):
    with transaction.atomic():
        actor = lock_actor(command.actor)
        model = command.model
        action = (
            "add"
            if command.pk is None
            else "change"
            if command.action == "save"
            else "transition"
        )
        if (
            not permitted(actor, model, action)
            or model in SHARED
            and not actor.is_superuser
        ):
            raise PermissionDenied()
        if command.pk is None:
            obj = model()
        else:
            obj = (
                related(scoped(model, actor, action))
                .select_for_update()
                .filter(pk=command.pk)
                .first()
            )
            if obj is None:
                raise NotFound()
            if command.expected_version != version(obj):
                raise StalePeopleVersion()
        before = snapshot(obj) if command.pk is not None else {}
        old = {
            f.attname: getattr(obj, f.attname)
            for f in model._meta.fields
            if not isinstance(f, (models.GeneratedField, models.CompositePrimaryKey))
        }
        values = dict(command.values)
        if len(command.reason) > 250:
            raise ValidationError({"reason": "Use at most 250 characters."})
        if command.action == "save":
            if set(values) - set(FIELDS[model]):
                raise ValidationError({"fields": "Unsupported or protected fields."})
            for name in set(values) & RESTRICTED:
                if not permitted(actor, model, "restricted"):
                    raise PermissionDenied("Restricted-field permission required.")
            for name in set(values) & CONFIDENTIAL:
                if not permitted(actor, model, "confidential"):
                    raise PermissionDenied("Confidential-field permission required.")
            immutable = {
                "institution_id",
                "student_id",
                "employee_id",
                "campus_id",
                "department_id",
            }
            if model is m.EmployeeCompetency:
                immutable.add("course_id")
            if command.pk is not None and any(
                name in values and values[name] != old.get(name) for name in immutable
            ):
                raise ValidationError(
                    "Ownership changes require a separate reviewed transfer workflow."
                )
            if (
                isinstance(obj, m.EmploymentSource)
                and command.pk
                and "is_external" in values
                and values["is_external"] != obj.is_external
                and m.Employee.objects.filter(employment_source=obj).exists()
            ):
                raise PeopleConflict(
                    "Referenced employment-source semantics cannot change."
                )
            for name, value in values.items():
                setattr(obj, name, value)
            if command.pk is None and isinstance(obj, m.EmployeeAssignment):
                obj.is_primary = False
        elif command.action == "status":
            if (
                model not in (m.Student, m.Employee)
                or set(values) != {"status"}
                or not command.reason.strip()
            ):
                raise ValidationError("Supply status and a reason.")
            field = "student_status" if model is m.Student else "employment_status"
            transitions = {
                m.Student: {
                    "APPLICANT": {"ACTIVE", "WITHDRAWN"},
                    "ACTIVE": {"SUSPENDED", "WITHDRAWN", "COMPLETED", "DECEASED"},
                    "SUSPENDED": {"ACTIVE", "WITHDRAWN", "DECEASED"},
                    "COMPLETED": {"ALUMNUS", "DECEASED"},
                    "WITHDRAWN": {"APPLICANT", "DECEASED"},
                    "ALUMNUS": {"DECEASED"},
                    "DECEASED": set(),
                },
                m.Employee: {
                    "DRAFT": {"ACTIVE"},
                    "ACTIVE": {
                        "ON_LEAVE",
                        "SUSPENDED",
                        "RESIGNED",
                        "RETIRED",
                        "TERMINATED",
                    },
                    "ON_LEAVE": {"ACTIVE", "RESIGNED", "TERMINATED"},
                    "SUSPENDED": {"ACTIVE", "RESIGNED", "TERMINATED"},
                    "RESIGNED": set(),
                    "RETIRED": set(),
                    "TERMINATED": set(),
                },
            }
            if values["status"] not in transitions[model].get(
                getattr(obj, field), set()
            ):
                raise PeopleConflict("Invalid lifecycle transition.")
            if values["status"] == "ACTIVE":
                activation_ready(obj)
            setattr(obj, field, values["status"])
        elif command.action in ("activate", "deactivate"):
            if not hasattr(obj, "is_active") or values or not command.reason.strip():
                raise ValidationError("Supply a reason only.")
            obj.is_active = command.action == "activate"
        else:
            raise ValidationError("Unsupported command.")
        obj.clean()
        check_primary_overlap(obj)
        parent_checks(obj, actor, old)
        obj.full_clean(
            exclude=[
                f.name
                for f in model._meta.fields
                if isinstance(f, models.GeneratedField)
            ]
        )
        obj.save()
        if not scoped(model, actor, action).filter(pk=obj.pk).exists():
            raise PermissionDenied("Record falls outside your scope.")
        root = owner(obj)
        if (
            isinstance(root, (m.Student, m.Employee))
            and getattr(
                root, "student_status", getattr(root, "employment_status", None)
            )
            == "ACTIVE"
        ):
            activation_ready(root)
        audit(
            obj,
            actor,
            "create" if command.pk is None else command.action,
            before,
            command.reason,
            command.source,
            tuple(values),
        )
        return obj


@stable_errors
def set_primary(model, pk, *, actor, expected_version, reason):
    if (
        model not in (m.StudentAddress, m.EmployeeAddress, m.EmployeeAssignment)
        or not reason.strip()
        or len(reason) > 250
    ):
        raise ValidationError(
            "A primary-capable record and bounded reason are required."
        )
    with transaction.atomic():
        actor = lock_actor(actor)
        obj = (
            related(scoped(model, actor, "transition"))
            .select_for_update()
            .filter(pk=pk)
            .first()
        )
        if obj is None:
            raise NotFound()
        if version(obj) != expected_version:
            raise StalePeopleVersion()
        start, end = (
            ("start_date", "end_date")
            if model is m.EmployeeAssignment
            else ("valid_from", "valid_to")
        )
        when = getattr(obj, start)
        if not when or when > timezone.localdate() or getattr(obj, end):
            raise ValidationError(
                "A current primary must start on or before today and have no end date."
            )
        name = "student" if model is m.StudentAddress else "employee"
        previous = (
            model.objects.select_for_update()
            .filter(
                **{
                    name + "_id": getattr(obj, name + "_id"),
                    "is_primary": True,
                    end + "__isnull": True,
                }
            )
            .exclude(pk=pk)
        )
        for row in previous:
            if not scoped(model, actor, "transition").filter(pk=row.pk).exists():
                raise PermissionDenied()
            if getattr(row, start) and getattr(row, start) >= when:
                raise PeopleConflict(
                    "New primary must start after the previous primary."
                )
            before = snapshot(row)
            setattr(row, end, when - timedelta(days=1))
            row.full_clean()
            row.save()
            audit(row, actor, "primary_closed", before, reason)
        before = snapshot(obj)
        obj.is_primary = True
        check_primary_overlap(obj)
        parent_checks(
            obj,
            actor,
            {
                f.attname: getattr(obj, f.attname)
                for f in obj._meta.fields
                if not isinstance(f, models.GeneratedField)
            },
        )
        obj.full_clean()
        obj.save()
        audit(obj, actor, "primary_selected", before, reason)
        return obj


@stable_errors
def bulk_save(model, rows, *, actor, reason):
    """Internal validated import boundary; all records succeed or none commit."""
    from .constants import MAX_BULK_ROWS

    if (
        not isinstance(rows, list)
        or not 1 <= len(rows) <= MAX_BULK_ROWS
        or not reason.strip()
    ):
        raise ValidationError("Supply 1-100 rows and a reason.")
    with transaction.atomic():
        actor = lock_actor(actor)
        return [
            execute(Command(model, actor, row, reason=reason, source="import"))
            for row in rows
        ]
