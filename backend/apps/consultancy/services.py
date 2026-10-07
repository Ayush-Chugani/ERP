import hashlib
import json
import re
from datetime import date
from functools import wraps
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from apps.identity_access.audit import record
from apps.identity_access.models import ActivityAudit
from apps.people_master.models import EmployeeAssignment
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_activities.workflow import status
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    VerificationStatus,
)

from .models import (
    ConsultancyProject,
    ProjectMilestone,
    ProjectReceipt,
    ProjectStatusHistory,
    ProjectTeam,
    ReceiptVoid,
)
from .permissions import principal, require

MODULE = "CONSULTANCY"
TYPE_CODE = "CONSULTANCY_PROJECT"
EDITABLE = {"PROPOSED", "APPROVED", "ONGOING", "COMPLETED"}
TRANSITIONS = {
    "approve": ({"PROPOSED"}, "APPROVED", "UPDATE"),
    "start": ({"APPROVED"}, "ONGOING", "UPDATE"),
    "complete": ({"ONGOING"}, "COMPLETED", "UPDATE"),
    "close": ({"COMPLETED"}, "CLOSED", "UPDATE"),
    "cancel": ({"PROPOSED", "APPROVED", "ONGOING"}, "CANCELLED", "UPDATE"),
}
CATEGORIES = (
    "PROPOSAL",
    "WORK_ORDER",
    "AGREEMENT",
    "PURCHASE_ORDER",
    "INVOICE",
    "COMPLETION_CERTIFICATE",
    "CLIENT_FEEDBACK",
    "OTHER",
)
FINANCIAL_FIELDS = {"consultancy_amount", "amount_received", "faculty_incentive_share"}
FINANCIAL_DOCUMENTS = {"INVOICE"}


class Conflict(APIException):
    status_code = 409
    default_detail = "The request conflicts with a newer edit or an earlier retry. Refresh the record."


def command(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            with transaction.atomic():
                return fn(*args, **kwargs)
        except ObjectDoesNotExist:
            raise NotFound() from None
        except IntegrityError:
            raise Conflict() from None
        except OperationalError as error:
            if error.args and error.args[0] in (1205, 1213):
                raise Conflict(
                    "Concurrent change; retry using the same request key."
                ) from None
            raise

    return run


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def version(pk):
    return digest(
        [
            ActivityAudit.objects.filter(
                module_code=MODULE, entity_name="staff_activity", entity_id=str(pk)
            )
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first(),
            StaffActivity.objects.values().get(pk=pk),
            ConsultancyProject.objects.values().get(pk=pk),
            list(
                ActivityAttachment.objects.filter(staff_activity_id=pk)
                .order_by("pk")
                .values()
            ),
        ]
    )


def locked(actor, pk, action, resource="ACTIVITY"):
    principal(actor)
    parent = StaffActivity.objects.select_for_update().get(
        pk=pk, deleted_at__isnull=True
    )
    actor = require(actor, resource, action, parent)
    if (
        parent.activity_type.activity_type_code != TYPE_CODE
        or parent.activity_type.activity_group != "CONSULTANCY"
    ):
        raise ValidationError("Activity has an incompatible specialization.")
    from apps.staff_activities.specialization import ensure_exclusive

    ensure_exclusive(parent, ConsultancyProject)
    ConsultancyProject.objects.get(pk=pk)
    return actor, parent


def editable(parent):
    if ConsultancyProject.objects.get(pk=parent.pk).status not in EDITABLE:
        raise ValidationError("Closed/cancelled projects cannot be changed.")


def check_version(parent, expected):
    if not expected or version(parent.pk) != expected:
        raise Conflict()


def retry(actor, key, operation, payload, execute, authorize, resource="ACTIVITY"):
    actor = principal(actor)
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", key):
        raise ValidationError("Supply an Idempotency-Key of 1-100 safe characters.")
    # Serialize this actor's commands, including the first receipt creation.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    fingerprint = digest(payload)
    receipt = ActivityCommandReceipt.objects.filter(actor=actor, key=key).first()
    if receipt:
        if receipt.operation != operation or receipt.digest != fingerprint:
            raise Conflict()
        actor, parent = locked(actor, receipt.staff_activity_id, authorize, resource)
        require(actor, "ACTIVITY", "READ", parent)
        if resource != "ACTIVITY":
            require(actor, resource, "READ", parent)
        if operation == "project.create" or resource == "FINANCE":
            require(actor, "FINANCE", "READ", parent)
        if operation == "project.create":
            require(actor, "FINANCE", "UPDATE", parent)
        return ConsultancyProject.objects.get(pk=parent.pk)
    row = execute()
    ActivityCommandReceipt.objects.create(
        actor=actor,
        key=key,
        operation=operation,
        digest=fingerprint,
        staff_activity_id=row.pk,
    )
    return row


def required_reason(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
        raise ValidationError({"reason": "Supply a reason of 1-1000 characters."})
    return value.strip()


def snapshot(row):
    return {
        f.attname: str(getattr(row, f.attname))
        if getattr(row, f.attname) is not None
        else None
        for f in row._meta.concrete_fields
    }


def audit(actor, parent, action, before=None, after=None, reason="", request_id=None):
    record(
        actor=actor,
        module=MODULE,
        action=action,
        entity=parent,
        before=before,
        after=after,
        details={"reason": reason},
        request_id=request_id or uuid4().hex,
    )


def validate_text(row):
    for field in row._meta.concrete_fields:
        value = getattr(row, field.attname)
        if (
            field.get_internal_type() == "TextField"
            and isinstance(value, str)
            and len(value.encode("utf-8")) > 65535
        ):
            raise ValidationError(
                {field.name: "Text exceeds the native TEXT byte limit."}
            )


def normalize(row):
    for field in row._meta.concrete_fields:
        value = getattr(row, field.attname)
        if isinstance(value, str):
            setattr(row, field.attname, value.strip())
        if field.get_internal_type() == "DecimalField":
            if isinstance(value, (float, bool)):
                raise ValidationError({field.name: "Use exact decimal strings."})
            value = field.clean(value, row)
            if value is not None and (not value.is_finite() or value < 0):
                raise ValidationError({field.name: "Use a nonnegative finite amount."})
            setattr(row, field.attname, value)
    row.currency_code = str(row.currency_code).upper()
    if not re.fullmatch(r"[A-Z]{3}", row.currency_code):
        raise ValidationError(
            {"currency_code": "Use an uppercase three-letter currency code."}
        )
    validate_text(row)
    row.full_clean(
        exclude=["staff_activity"], validate_unique=False, validate_constraints=False
    )
    if not row.client_organization.is_active:
        raise ValidationError("Select an active client organization.")
    if (
        row.principal_consultant_employee_id != row.staff_activity.employee_id
        or row.principal_consultant_employee.employment_status != "ACTIVE"
    ):
        raise ValidationError(
            "The principal consultant must match the active parent employee."
        )


def apply(row, values):
    allowed = {f.attname for f in row._meta.concrete_fields if not f.primary_key} - {
        "principal_consultant_employee_id",
        "status",
        "amount_received",
    }
    if set(values) - allowed:
        raise ValidationError("Unknown or protected project field.")
    for key, value in values.items():
        setattr(row, key, value)


@command
def save_activity(
    actor,
    values,
    *,
    context=None,
    activity_id=None,
    expected_version=None,
    key=None,
    reason="",
    request_id=None,
):
    actor = principal(actor)
    context = context or {}
    if activity_id:
        actor, parent = locked(actor, activity_id, "UPDATE")
        require(actor, "ACTIVITY", "READ", parent)
        check_version(parent, expected_version)
        editable(parent)
        if context:
            raise ValidationError("Ownership context is immutable.")
        row = ConsultancyProject.objects.get(pk=activity_id)
        before = snapshot(row)
        if set(values) & (FINANCIAL_FIELDS | {"currency_code"}):
            require(actor, "FINANCE", "UPDATE", parent)
            require(actor, "FINANCE", "READ", parent)
        if (
            "currency_code" in values
            and values["currency_code"] != row.currency_code
            and ProjectReceipt.objects.filter(project=row).exists()
        ):
            raise ValidationError(
                "Currency is immutable after receipt reporting begins."
            )
        apply(row, values)
        normalize(row)
        validate_children(row)
        parent.activity_title = row.consultancy_title
        parent.updated_by_user = actor
        parent.save()
        row.save()
        audit(
            actor,
            parent,
            "UPDATE",
            before,
            snapshot(row),
            required_reason(reason),
            request_id,
        )
        return row
    if set(context) - {"employee_assignment_id", "academic_year_id", "context_date"}:
        raise ValidationError("Unknown parent context.")

    def create():
        try:
            start = (
                date.fromisoformat(context["context_date"])
                if isinstance(context["context_date"], str)
                else context["context_date"]
            )
        except (KeyError, TypeError, ValueError):
            raise ValidationError(
                {"context_date": "Supply a valid PI assignment context date."}
            ) from None
        if not isinstance(start, date):
            raise ValidationError("Invalid context date.")
        assignment = (
            EmployeeAssignment.objects.select_for_update()
            .select_related("employee", "campus")
            .get(pk=context.get("employee_assignment_id"))
        )
        if (
            assignment.employee.institution_id != assignment.campus.institution_id
            or not assignment.department_id
            or assignment.employee.employment_status != "ACTIVE"
            or assignment.start_date > start
            or (assignment.end_date and assignment.end_date < start)
        ):
            raise ValidationError(
                "Select an active consultant assignment valid on the context date."
            )
        parent = StaffActivity(
            employee=assignment.employee,
            institution_id=assignment.employee.institution_id,
            campus_id=assignment.campus_id,
            department_id=assignment.department_id,
            activity_type=ActivityType.objects.get(
                activity_type_code=TYPE_CODE,
                activity_group="CONSULTANCY",
                is_active=True,
            ),
            academic_year_id=context.get("academic_year_id"),
            start_date=start,
            approval_status=status(ApprovalStatus, "DRAFT"),
            verification_status=status(VerificationStatus, "PENDING"),
            created_by_user=actor,
            updated_by_user=actor,
        )
        for resource, action in [
            ("ACTIVITY", "CREATE"),
            ("ACTIVITY", "READ"),
            ("FINANCE", "UPDATE"),
            ("FINANCE", "READ"),
        ]:
            require(actor, resource, action, parent)
        row = ConsultancyProject(
            staff_activity=parent, principal_consultant_employee=assignment.employee
        )
        apply(row, values)
        normalize(row)
        parent.activity_title = row.consultancy_title
        parent.full_clean(validate_unique=False, validate_constraints=False)
        parent.save()
        row.staff_activity = parent
        row.save()
        ProjectStatusHistory.objects.create(
            project=row,
            to_status=row.status,
            changed_by=actor,
            remarks="Project proposed",
        )
        audit(actor, parent, "CREATE", after=snapshot(row), request_id=request_id)
        return row

    return retry(
        actor,
        key,
        "project.create",
        {"context": context, "activity": values},
        create,
        "CREATE",
    )


@command
def workflow(actor, pk, action, remarks, expected_version, key, request_id=None):
    if action not in TRANSITIONS:
        raise ValidationError("Unsupported transition.")
    remarks = required_reason(remarks)

    def execute():
        fresh, parent = locked(actor, pk, "UPDATE", "STATUS")
        require(fresh, "ACTIVITY", "READ", parent)
        check_version(parent, expected_version)
        row = ConsultancyProject.objects.get(pk=pk)
        sources, target, _ = TRANSITIONS[action]
        if row.status not in sources:
            raise ValidationError("Transition not allowed from current status.")
        before = row.status
        row.status = target
        normalize(row)
        # Project execution status is distinct from the parent approval decision.
        if action == "approve":
            parent.approval_status = status(ApprovalStatus, "APPROVED")
            parent.approved_by_user = fresh
            parent.approved_at = timezone.now()
            parent.approval_remarks = remarks
        parent.updated_by_user = fresh
        parent.save()
        row.save(update_fields=["status"])
        ProjectStatusHistory.objects.create(
            project=row,
            from_status=before,
            to_status=target,
            changed_by=fresh,
            remarks=remarks,
        )
        audit(
            fresh,
            parent,
            "UPDATE",
            {"status": before},
            {"status": target},
            remarks,
            request_id,
        )
        return row

    return retry(
        actor,
        key,
        "project." + action,
        {"pk": str(pk), "version": expected_version, "remarks": remarks},
        execute,
        "UPDATE",
        "STATUS",
    )


@command
def archive(actor, pk, expected_version):
    actor, parent = locked(actor, pk, "DELETE")
    require(actor, "ACTIVITY", "READ", parent)
    check_version(parent, expected_version)
    if ConsultancyProject.objects.get(pk=pk).status not in {"CANCELLED", "CLOSED"}:
        raise ValidationError("Only cancelled/closed projects can be archived.")
    parent.deleted_at = timezone.now()
    parent.deleted_by_user = actor
    parent.updated_by_user = actor
    parent.save()
    audit(actor, parent, "DELETE")


def validate_children(project):
    for row in ProjectTeam.objects.filter(project=project):
        validate_team(row, project)
    for row in ProjectMilestone.objects.filter(project=project):
        validate_milestone(row, project)


def validate_team(row, project):
    if row.employee.institution_id != project.staff_activity.institution_id or (
        row.is_active and row.employee.employment_status != "ACTIVE"
    ):
        raise ValidationError(
            "Team employee must belong to the institution and be active for active membership."
        )
    if row.employee_id == project.principal_consultant_employee_id:
        raise ValidationError(
            "The principal is already authoritative in the project; select a co-consultant."
        )
    if (
        row.start_date < project.project_start_date
        or (row.end_date and row.end_date < row.start_date)
        or (
            project.completion_date
            and (
                row.start_date > project.completion_date
                or (row.end_date and row.end_date > project.completion_date)
            )
        )
    ):
        raise ValidationError("Team dates must fit project dates.")


def validate_milestone(row, project):
    for value in (row.due_date, row.completion_date, row.acceptance_date):
        if value and (
            value < project.project_start_date
            or (project.completion_date and value > project.completion_date)
        ):
            raise ValidationError("Milestone dates must fit known project dates.")
    if row.status in {"COMPLETED", "ACCEPTED"} and not row.completion_date:
        raise ValidationError("Completed milestones require a completion date.")
    if row.status == "ACCEPTED" and not row.acceptance_date:
        raise ValidationError("Accepted milestones require an acceptance date.")
    if row.acceptance_date and (
        not row.completion_date or row.acceptance_date < row.completion_date
    ):
        raise ValidationError("Acceptance must follow completion.")


@command
def extension(
    actor,
    pk,
    kind,
    values,
    *,
    expected_version,
    reason,
    key,
    item_id=None,
    void=False,
    request_id=None,
):
    reason = required_reason(reason)
    configs = {
        "team": (ProjectTeam, "TEAM"),
        "milestones": (ProjectMilestone, "MILESTONE"),
        "receipts": (ProjectReceipt, "FINANCE"),
    }
    if kind not in configs:
        raise ValidationError("Unsupported extension.")
    model, resource = configs[kind]
    action = "DELETE" if void else "UPDATE"

    def execute():
        fresh, parent = locked(actor, pk, action, resource)
        require(fresh, "ACTIVITY", "READ", parent)
        require(fresh, resource, "READ", parent)
        check_version(parent, expected_version)
        if kind != "receipts":
            editable(parent)
        project = ConsultancyProject.objects.get(pk=pk)
        row = (
            model.objects.get(pk=item_id, project=project)
            if item_id
            else model(project=project)
        )
        before = snapshot(row) if row.pk else None
        if (
            kind == "team"
            and row.pk
            and "employee_id" in values
            and str(values["employee_id"]) != str(row.employee_id)
        ):
            raise ValidationError(
                "Team membership employee is immutable; deactivate and add a new member."
            )
        if kind == "receipts" and item_id:
            if not void or values:
                raise ValidationError(
                    "Receipts are immutable: void and replace with a new reference."
                )
            ReceiptVoid.objects.create(receipt=row, actor=fresh, reason=reason)
        else:
            if void:
                raise ValidationError(
                    "Deactivate team members or cancel milestones through an update."
                )
            allowed = {
                f.attname for f in model._meta.concrete_fields if not f.primary_key
            } - {"project_id", "actor_id", "created_at"}
            if set(values) - allowed:
                raise ValidationError("Unknown or protected extension field.")
            for name, value in values.items():
                if isinstance(value, float) or (
                    kind == "receipts" and name == "amount" and isinstance(value, bool)
                ):
                    raise ValidationError("Use exact decimal strings.")
                setattr(row, name, value.strip() if isinstance(value, str) else value)
            if kind == "receipts":
                row.actor = fresh
                row.currency_code = str(row.currency_code).upper()
            validate_text(row)
            row.full_clean(
                exclude=["created_at"], validate_unique=False, validate_constraints=True
            )
            if kind == "team":
                validate_team(row, project)
            elif kind == "milestones":
                validate_milestone(row, project)
            else:
                if row.currency_code != project.currency_code:
                    raise ValidationError("Receipt currency must match project.")
                if row.document_attachment_id:
                    link = ActivityAttachment.objects.get(
                        pk=row.document_attachment_id, staff_activity=parent
                    )
                    require(fresh, "DOCUMENT", "READ", parent)
                    from apps.documents_exit.sharing import inspect_shared

                    inspect_shared(
                        actor=fresh,
                        file_id=link.file_object_id,
                        institution_id=parent.institution_id,
                    )
            row.save()
        if kind == "receipts":
            from decimal import Decimal

            from django.db.models import Sum

            total = ProjectReceipt.objects.filter(
                project=project, void_record__isnull=True
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            ConsultancyProject._meta.get_field("amount_received").clean(total, project)
            project.amount_received = total
            project.save(update_fields=["amount_received"])
        row.refresh_from_db()
        audit(
            fresh,
            parent,
            action,
            before,
            {**snapshot(row), "kind": kind, "void": void},
            reason,
            request_id,
        )
        return project

    return retry(
        actor,
        key,
        "consultancy." + kind + "." + action,
        {
            "pk": str(pk),
            "id": str(item_id),
            "values": values,
            "version": expected_version,
            "reason": reason,
            "void": void,
        },
        execute,
        action,
        resource,
    )


def metrics(row):
    from decimal import Decimal

    return {
        "balance_receivable": str(row.consultancy_amount - row.amount_received),
        "collection_percentage": str(
            (row.amount_received / row.consultancy_amount * 100).quantize(
                Decimal("0.01")
            )
        )
        if row.consultancy_amount
        else None,
    }


def upload_attachment(
    *, actor, pk, expected_version, upload, title, category, replaces=None
):
    from apps.documents_exit.sharing import upload_shared

    def authorize(fresh):
        fresh, parent = locked(fresh, pk, "UPDATE", "DOCUMENT")
        require(fresh, "ACTIVITY", "READ", parent)
        require(fresh, "DOCUMENT", "READ", parent)
        if category in FINANCIAL_DOCUMENTS:
            require(fresh, "FINANCE", "READ", parent)
        check_version(parent, expected_version)
        if (
            category not in CATEGORIES
            or not isinstance(title, str)
            or not 1 <= len(title.strip()) <= 200
        ):
            raise ValidationError(
                "Select an evidence category and title of at most 200 characters."
            )
        if replaces:
            ActivityAttachment.objects.get(
                pk=replaces, staff_activity=parent, replacement__isnull=True
            )
        return parent

    def attach(fresh, parent, file):
        link = ActivityAttachment.objects.create(
            staff_activity=parent,
            file_object=file,
            title=title.strip(),
            category=category,
            replaces_id=replaces,
        )
        record(
            actor=fresh,
            module=MODULE,
            action="UPDATE",
            entity=parent,
            details={"attachment_id": link.pk, "replaces_id": replaces},
        )
        return link

    # Evidence is always RESTRICTED and subject to M13 file-level permissions.
    return upload_shared(
        actor=actor,
        upload=upload,
        level="RESTRICTED",
        authorize=authorize,
        attach=attach,
    )


def download_attachment(*, actor, pk, attachment_id):
    from apps.documents_exit.sharing import download_shared

    def authorize(fresh):
        _, parent = locked(fresh, pk, "READ", "DOCUMENT")
        require(fresh, "ACTIVITY", "READ", parent)
        link = ActivityAttachment.objects.get(pk=attachment_id, staff_activity=parent)
        if link.category in FINANCIAL_DOCUMENTS:
            require(fresh, "FINANCE", "READ", parent)
        ActivityAttachment.objects.get(pk=attachment_id, staff_activity=parent)
        return parent

    # Authorization happens before exposing a file identifier to the storage API.
    principal(actor)
    require(
        actor,
        "ACTIVITY",
        "READ",
        StaffActivity.objects.get(pk=pk, deleted_at__isnull=True),
    )
    link = ActivityAttachment.objects.get(pk=attachment_id, staff_activity_id=pk)
    return download_shared(
        actor=actor, file_id=link.file_object_id, authorize=authorize
    )
