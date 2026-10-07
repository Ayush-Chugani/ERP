import logging
import re
import uuid
from datetime import timedelta
from functools import wraps
from time import perf_counter

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as ModelError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.people_master.models import Employee

from . import audit, policies
from . import models as m
from . import permissions as p

logger = logging.getLogger(__name__)


class Conflict(APIException):
    status_code = 409
    default_detail = "Support workflow conflicts with current state. Refresh and retry."
    default_code = "support_conflict"


def command(fn):
    @wraps(fn)
    @sensitive_variables()
    def run(*, actor, **values):
        started = perf_counter()
        outcome = "failed"
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(
                    app_label="organization", model="university"
                )
                actor = get_user_model().objects.get(pk=actor.pk)
                if not settings.STUDENT_SUPPORT_ENABLED or not actor.is_active:
                    raise PermissionDenied()
                result = fn(actor=actor, **values)
                outcome = "ok"
                return result
        except ObjectDoesNotExist:
            raise NotFound("Support record unavailable.") from None
        except (ModelError, ValueError, TypeError):
            raise ValidationError(
                "Invalid support input. Check dates, field lengths and allowed values."
            ) from None
        except (IntegrityError, OperationalError) as error:
            if error.args and error.args[0] in [
                1062,
                1451,
                1452,
                1205,
                1213,
                3819,
                4025,
            ]:
                raise Conflict() from None
            raise
        finally:
            logger.info(
                "student_support_operation",
                extra={
                    "operation": fn.__name__,
                    "outcome": outcome,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )

    return run


def save(obj):
    obj.full_clean()
    obj.save()
    return obj


def narrative(value, required=False):
    if value is None or not str(value).strip():
        if required:
            raise ValidationError("A narrative is required for this action.")
        return None
    if not isinstance(value, str) or len(value.encode("utf-8")) > 60000:
        raise ValidationError("Text exceeds the supported byte limit.")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValidationError("Unsupported text characters.")
    return value.strip()


def assignment_dates(student, start, end, exclude=None):
    if end and end < start:
        raise ValidationError("End date must not precede start date.")
    if not policies.policy(student.institution_id, "allow_overlapping_mentors", True):
        qs = m.MentorAssignment.objects.filter(
            student=student, assignment_status="ACTIVE"
        ).exclude(pk=exclude)
        if end:
            qs = qs.filter(start_date__lte=end)
        qs = qs.filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
        if qs.exists():
            raise Conflict("The assignment overlaps an active mentor assignment.")


@command
def assign_mentor(*, actor, student_id, employee_id, start_date, end_date=None):
    student = p.get(p.students(actor, "manage_mentor_assignments"), student_id, True)
    employee = Employee.objects.filter(
        pk=employee_id,
        institution_id=student.institution_id,
        employment_status="ACTIVE",
    ).first()
    if not employee or student.student_status != "ACTIVE":
        raise NotFound("Active student and mentor required.")
    assignment_dates(student, start_date, end_date)
    obj = save(
        m.MentorAssignment(
            student=student, employee=employee, start_date=start_date, end_date=end_date
        )
    )
    audit.emit(actor, obj, "mentor_created", status=obj.assignment_status)
    return obj


@command
def end_assignment(*, actor, pk, expected_status, end_date, cancel=False):
    obj = p.get(p.assignments(actor, "manage_mentor_assignments"), pk, True)
    if obj.assignment_status != expected_status or obj.assignment_status != "ACTIVE":
        raise Conflict()
    if end_date < obj.start_date:
        raise ValidationError("End date must not precede start date.")
    obj.end_date = end_date
    obj.assignment_status = "CANCELLED" if cancel else "COMPLETED"
    save(obj)
    audit.emit(
        actor,
        obj,
        "mentor_cancelled" if cancel else "mentor_ended",
        status=obj.assignment_status,
    )
    return obj


@command
def change_mentor(*, actor, pk, expected_status, employee_id, start_date):
    old = p.get(p.assignments(actor, "manage_mentor_assignments"), pk, True)
    if start_date <= old.start_date:
        raise ValidationError(
            "A replacement starts after the original assignment start."
        )
    end_assignment(
        actor=actor,
        pk=pk,
        expected_status=expected_status,
        end_date=start_date - timedelta(days=1),
    )
    return assign_mentor(
        actor=actor,
        student_id=old.student_id,
        employee_id=employee_id,
        start_date=start_date,
    )


def conduct_assignment(actor, assignment):
    if not p.can(actor, "conduct_counselling"):
        raise NotFound()
    if actor.is_superuser:
        return
    try:
        employee = p.identity(actor, "employee", True)
        if (
            employee.pk == assignment.employee_id
            and employee.institution_id == assignment.student.institution_id
        ):
            return
    except NotFound:
        pass
    if (
        not p.students(actor, "view_counselling_all")
        .filter(pk=assignment.student_id)
        .exists()
    ):
        raise NotFound()


def session_rules(obj):
    assignment = obj.mentor_assignment
    day = timezone.localtime(obj.session_date).date()
    if policies.policy(
        assignment.student.institution_id, "session_within_assignment", True
    ) and (
        day < assignment.start_date
        or (assignment.end_date and day > assignment.end_date)
    ):
        raise ValidationError("Session date is outside the assignment period.")
    if obj.follow_up_date and obj.follow_up_date < day:
        raise ValidationError("Follow-up must not precede the session date.")
    if obj.session_status == "FOLLOW_UP_REQUIRED" and not obj.follow_up_date:
        raise ValidationError("A follow-up date is required.")
    if (
        obj.session_status in ["COMPLETED", "FOLLOW_UP_REQUIRED"]
        and obj.session_date > timezone.now()
    ):
        raise ValidationError("A future session cannot be completed.")


@command
def schedule_session(
    *, actor, mentor_assignment_id, session_date, confidentiality_level="RESTRICTED"
):
    assignment = p.get(
        (
            p.assignments(actor) | p.assignments(actor, "view_counselling_all")
        ).distinct(),
        mentor_assignment_id,
        True,
    )
    conduct_assignment(actor, assignment)
    if (
        assignment.assignment_status != "ACTIVE"
        or assignment.student.student_status != "ACTIVE"
        or assignment.employee.employment_status != "ACTIVE"
    ):
        raise Conflict("An active assignment and people are required.")
    if not p.can(actor, "view_counselling_" + confidentiality_level.lower()):
        raise NotFound()
    obj = m.CounsellingSession(
        mentor_assignment=assignment,
        session_date=session_date,
        session_status="SCHEDULED",
        confidentiality_level=confidentiality_level,
    )
    session_rules(obj)
    save(obj)
    audit.emit(
        actor,
        obj,
        "session_created",
        status=obj.session_status,
        confidentiality_level=obj.confidentiality_level,
    )
    return obj


@command
def session_action(
    *,
    actor,
    pk,
    expected_status,
    action,
    observations=None,
    action_plan=None,
    follow_up_date=None,
    session_date=None,
    confidentiality_level=None,
):
    obj = p.get(p.sessions(actor, write=True), pk, True)
    if obj.session_status != expected_status:
        raise Conflict()
    before = obj.session_status
    if action == "confidentiality":
        if not p.can(actor, "change_counselling_confidentiality") or not p.can(
            actor, "view_counselling_" + str(confidentiality_level).lower()
        ):
            raise NotFound()
        previous = obj.confidentiality_level
        obj.confidentiality_level = confidentiality_level
        save(obj)
        audit.emit(
            actor,
            obj,
            "session_confidentiality",
            previous_level=previous,
            confidentiality_level=obj.confidentiality_level,
        )
        return obj
    if action == "reschedule":
        if before != "SCHEDULED" or session_date is None:
            raise Conflict()
        obj.session_date = session_date
    elif action == "cancel":
        if before != "SCHEDULED":
            raise Conflict()
        obj.session_status = "CANCELLED"
    elif action in ["complete", "follow-up"]:
        if before not in (
            ["SCHEDULED", "FOLLOW_UP_REQUIRED"]
            if action == "complete"
            else ["SCHEDULED", "COMPLETED"]
        ):
            raise Conflict()
        obj.session_status = (
            "COMPLETED" if action == "complete" else "FOLLOW_UP_REQUIRED"
        )
        if observations is not None:
            obj.observations = narrative(observations)
        if action_plan is not None:
            obj.action_plan = narrative(action_plan)
        obj.follow_up_date = follow_up_date if action == "follow-up" else None
    else:
        raise ValidationError("Unsupported session action.")
    session_rules(obj)
    save(obj)
    audit.emit(
        actor,
        obj,
        "session_" + action,
        previous_status=before,
        status=obj.session_status,
    )
    return obj


@command
def category_write(*, actor, category_code, category_name, is_active=True, pk=None):
    p.category_admin(actor)
    obj = (
        p.get(m.GrievanceCategory.objects.all(), pk, True)
        if pk
        else m.GrievanceCategory()
    )
    obj.category_code = category_code.strip().upper()
    obj.category_name = " ".join(category_name.split())
    obj.is_active = is_active
    save(obj)
    audit.emit(actor, obj, "category_updated" if pk else "category_created")
    return obj


class GrievanceNumberGenerator:
    @staticmethod
    def next():
        prefix = settings.STUDENT_SUPPORT_NUMBER_PREFIX
        if not re.fullmatch(r"[A-Z0-9-]{1,5}", prefix):
            raise ValidationError("Numbering configuration is invalid.")
        return prefix + "-" + uuid.uuid4().hex[:24].upper()


@command
@sensitive_variables()
def submit_grievance(
    *,
    actor,
    grievance_category_id,
    subject,
    description,
    department_id=None,
    priority="NORMAL",
):
    if not p.can(actor, "submit_own_grievance"):
        raise NotFound()
    student = p.identity(actor, "student", True)
    category = p.get(
        m.GrievanceCategory.objects.filter(is_active=True), grievance_category_id
    )
    if department_id is not None:
        from apps.organization.models import Department

        if not Department.objects.filter(
            pk=department_id,
            campus__institution_id=student.institution_id,
            is_active=True,
            campus__is_active=True,
        ).exists():
            raise NotFound()
    obj = None
    for attempt in range(5):
        try:
            with transaction.atomic():
                candidate = m.Grievance(
                    student=student,
                    grievance_category=category,
                    department_id=department_id,
                    subject=subject.strip(),
                    description=narrative(description, True),
                    priority=priority,
                    grievance_number=GrievanceNumberGenerator.next(),
                    submitted_at=timezone.now().replace(microsecond=0),
                )
                candidate.full_clean(validate_unique=False)
                candidate.save(force_insert=True)
                obj = candidate
            break
        except IntegrityError as error:
            if not error.args or error.args[0] != 1062:
                raise
            logger.warning("student_support_number_collision")
    if obj is None:
        raise Conflict("Unable to allocate grievance number; retry.")
    row = m.GrievanceAction.objects.create(
        grievance=obj, action_type="SUBMITTED", new_status="SUBMITTED"
    )
    audit.emit(actor, obj, "grievance_created", status=obj.status, history_id=row.pk)
    return obj


@command
@sensitive_variables()
def grievance_action(
    *,
    actor,
    pk,
    expected_status,
    action,
    notes=None,
    resolution=None,
    department_id=None,
):
    target = {
        "assign": "ASSIGNED",
        "review": "UNDER_REVIEW",
        "resolve": "RESOLVED",
        "reject": "REJECTED",
        "close": "CLOSED",
    }.get(action)
    if not target:
        raise ValidationError("Unsupported grievance action.")
    cap = (
        "resolve_grievance"
        if action == "resolve"
        else "close_grievance"
        if action == "close"
        else "triage_grievance"
    )
    obj = p.get(p.grievances(actor, cap), pk, True)
    if obj.status != expected_status or target not in policies.TRANSITIONS[obj.status]:
        raise Conflict()
    note = narrative(notes, action in ["assign", "reject"])
    old = obj.status
    if action == "assign":
        if department_id is None or not p.department_allowed(
            actor, department_id, cap, obj.student.institution_id
        ):
            raise NotFound()
        obj.department_id = department_id
    elif department_id is not None:
        raise ValidationError("Routing is available only through assign.")
    if target == "RESOLVED":
        obj.resolution = narrative(resolution, True)
        obj.resolved_at = timezone.now().replace(microsecond=0)
    elif resolution is not None:
        raise ValidationError("Resolution is available only through resolve.")
    if target not in ["RESOLVED", "CLOSED"]:
        obj.resolution = None
        obj.resolved_at = None
    obj.status = target
    save(obj)
    row = m.GrievanceAction.objects.create(
        grievance=obj,
        action_type="REVIEW_STARTED" if target == "UNDER_REVIEW" else target,
        action_notes=note,
        new_status=target,
    )
    audit.emit(
        actor,
        obj,
        "grievance_" + action,
        previous_status=old,
        status=target,
        history_id=row.pk,
    )
    return obj
