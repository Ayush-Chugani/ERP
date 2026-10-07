"""Shared staff-activity status transitions. Callers provide scoped authorization."""

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.identity_access.audit import record
from apps.people_master.models import AccountLink
from apps.staff_profile.models import ApprovalStatus, VerificationStatus

TRANSITIONS = {
    "submit": ({"DRAFT", "RETURNED"}, "SUBMITTED", "UPDATE"),
    "withdraw": ({"DRAFT", "RETURNED", "SUBMITTED"}, "WITHDRAWN", "UPDATE"),
    "review": ({"SUBMITTED"}, "UNDER_REVIEW", "VERIFY"),
    "return": ({"SUBMITTED", "UNDER_REVIEW", "VERIFIED"}, "RETURNED", "VERIFY"),
    "verify": ({"SUBMITTED", "UNDER_REVIEW"}, "VERIFIED", "VERIFY"),
    "approve": ({"VERIFIED"}, "APPROVED", "APPROVE"),
    "reject": ({"SUBMITTED", "UNDER_REVIEW", "VERIFIED"}, "REJECTED", "APPROVE"),
}


def status(model, code):
    value = model.objects.filter(status_code=code, is_active=True).first()
    if value is None:
        raise ValidationError(
            "Required active workflow status is not configured: " + code
        )
    return value


def transition(*, actor, parent, command, remarks, authorize, module):
    if command not in TRANSITIONS:
        raise ValidationError("Unsupported workflow action.")
    sources, target, action = TRANSITIONS[command]
    actor = authorize(actor, "ACTIVITY", action, parent)
    if action in {"VERIFY", "APPROVE"} and (
        parent.created_by_user_id == actor.pk
        or AccountLink.objects.filter(
            user=actor, employee_id=parent.employee_id
        ).exists()
    ):
        raise PermissionDenied("An independent reviewer is required.")
    if parent.approval_status.status_code not in sources:
        raise ValidationError("This workflow action is not valid in the current state.")
    if (
        not isinstance(remarks, str)
        or len(remarks) > 1000
        or (
            command in {"return", "reject", "verify", "approve"} and not remarks.strip()
        )
    ):
        raise ValidationError("Supply remarks of at most 1,000 characters.")
    before = parent.approval_status.status_code
    parent.approval_status = status(ApprovalStatus, target)
    parent.approval_remarks = remarks.strip()
    if command == "verify":
        parent.verification_status = status(VerificationStatus, "VERIFIED")
        parent.verified_by_user = actor
        parent.verified_at = timezone.now()
        parent.verification_remarks = remarks.strip()
    if command in {"return", "submit"}:
        parent.verification_status = status(VerificationStatus, "PENDING")
        parent.verified_by_user = None
        parent.verified_at = None
        parent.verification_remarks = None
    if command in {"approve", "reject"}:
        parent.approved_by_user = actor
        parent.approved_at = timezone.now()
        parent.approval_remarks = remarks.strip()
        parent.rejection_reason = remarks.strip() if command == "reject" else None
    parent.updated_by_user = actor
    parent.save()
    record(
        actor=actor,
        module=module,
        action=action,
        entity=parent,
        before={"status": before},
        after={"status": target},
        details={"command": command},
    )
    # Rationale stays on protected parent fields; no private free text in general audit.
