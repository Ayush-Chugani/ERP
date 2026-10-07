from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from rest_framework.exceptions import ValidationError

from . import audit
from . import models as m
from . import permissions as p
from . import services as s


def summary(obj):
    if isinstance(obj, m.MentorAssignment):
        return {
            "id": str(obj.pk),
            "student_id": str(obj.student_id),
            "employee_id": str(obj.employee_id),
            "start_date": obj.start_date,
            "end_date": obj.end_date,
            "status": obj.assignment_status,
        }
    if isinstance(obj, m.CounsellingSession):
        return {
            "id": str(obj.pk),
            "mentor_assignment_id": str(obj.mentor_assignment_id),
            "session_date": obj.session_date,
            "follow_up_date": obj.follow_up_date,
            "status": obj.session_status,
            "confidentiality_level": obj.confidentiality_level,
        }
    if isinstance(obj, m.Grievance):
        return {
            "id": str(obj.pk),
            "number": obj.grievance_number,
            "category_id": str(obj.grievance_category_id),
            "department_id": str(obj.department_id) if obj.department_id else None,
            "submitted_at": obj.submitted_at,
            "priority": obj.priority,
            "status": obj.status,
            "resolved_at": obj.resolved_at,
        }
    return {
        "id": str(obj.pk),
        "category_code": obj.category_code,
        "category_name": obj.category_name,
        "is_active": obj.is_active,
    }


@s.command
def session_detail(*, actor, pk):
    obj = p.get(p.sessions(actor), pk, True)
    audit.emit(
        actor, obj, "session_read", confidentiality_level=obj.confidentiality_level
    )
    return {
        **summary(obj),
        "observations": obj.observations,
        "action_plan": obj.action_plan,
    }


@s.command
def grievance_detail(*, actor, pk, own=False):
    obj = p.get(p.grievances(actor, own=own), pk, True)
    audit.emit(actor, obj, "grievance_read")
    # History has its own paginated endpoint; never expose an unbounded nested list.
    return {
        **summary(obj),
        "subject": obj.subject,
        "description": obj.description,
        "resolution": obj.resolution,
    }


def report(actor, submitted_from=None, submitted_to=None):
    qs = p.grievances(actor, "view_grievance_reports")
    if submitted_from:
        qs = qs.filter(submitted_at__date__gte=submitted_from)
    if submitted_to:
        qs = qs.filter(submitted_at__date__lte=submitted_to)
    if submitted_from and submitted_to and submitted_to < submitted_from:
        raise ValidationError("Invalid date range.")
    counts = list(
        qs.values("status", "grievance_category_id", "department_id")
        .annotate(count=Count("pk"))
        .order_by("status", "grievance_category_id", "department_id")[:501]
    )
    if len(counts) > 500:
        raise ValidationError("Narrow report date or authorization scope.")
    duration = ExpressionWrapper(
        F("resolved_at") - F("submitted_at"), output_field=DurationField()
    )
    value = qs.filter(resolved_at__isnull=False).aggregate(mean=Avg(duration))["mean"]
    return {
        "population": "Authorized grievances filtered by submission date; turnaround includes rows with resolved_at.",
        "groups": counts,
        "mean_resolution_seconds": value.total_seconds() if value else None,
        "sla": "No institutional SLA configured.",
    }
