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
    ResearchStatus,
    VerificationStatus,
)

from .models import (
    FundedResearchProject,
    ProjectStatusHistory,
    ResearchProjectFinancialUtilization,
    UtilizationVoid,
)
from .permissions import principal, require

MODULE = "FUNDED_PROJECTS"
TYPE_CODE = "FUNDED_RESEARCH_PROJECT"
EDITABLE = {"SANCTIONED", "ONGOING"}
TRANSITIONS = {
    "start": ({"SANCTIONED"}, "ONGOING", "UPDATE"),
    "complete": ({"ONGOING"}, "COMPLETED", "UPDATE"),
    "close": ({"COMPLETED"}, "CLOSED", "UPDATE"),
    "cancel": ({"SANCTIONED", "ONGOING"}, "CANCELLED", "UPDATE"),
}
CATEGORIES = (
    "SANCTION_ORDER",
    "UTILIZATION_CERTIFICATE",
    "STATEMENT_OF_EXPENDITURE",
    "COMPLETION_REPORT",
    "OTHER",
)
FINANCIAL_FIELDS = {
    "requested_amount",
    "sanctioned_amount",
    "amount_received",
    "amount_utilized",
    "utilization_summary",
}


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
            FundedResearchProject.objects.values().get(pk=pk),
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
        or parent.activity_type.activity_group != "RESEARCH"
    ):
        raise ValidationError("Activity has an incompatible specialization.")
    from apps.staff_activities.specialization import ensure_exclusive

    ensure_exclusive(parent, FundedResearchProject)
    FundedResearchProject.objects.get(pk=pk)
    return actor, parent


def editable(parent):
    row = (
        FundedResearchProject.objects.filter(pk=parent.pk)
        .select_related("research_status")
        .first()
    )
    if row and (
        not row.research_status.is_active
        or row.research_status.status_code not in EDITABLE
    ):
        raise ValidationError("Only sanctioned or ongoing projects can be edited.")


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
        if operation == "project.create" or resource == "FINANCE":
            require(actor, "FINANCE", "READ", parent)
        if operation == "project.create":
            require(actor, "FINANCE", "UPDATE", parent)
        return FundedResearchProject.objects.get(pk=parent.pk)
    row = execute()
    ActivityCommandReceipt.objects.create(
        actor=actor,
        key=key,
        operation=operation,
        digest=fingerprint,
        staff_activity_id=row.pk,
    )
    return row


def normalize(row):
    from decimal import Decimal

    from django.conf import settings

    for field in row._meta.concrete_fields:
        value = getattr(row, field.attname)
        if isinstance(value, str):
            setattr(row, field.attname, value.strip())
        if field.get_internal_type() == "DecimalField":
            if isinstance(value, (float, bool)):
                raise ValidationError({field.name: "Use exact decimal strings."})
            value = field.clean(value, row)
            if value is not None and (not value.is_finite() or value < Decimal(0)):
                raise ValidationError({field.name: "Use a nonnegative finite amount."})
            setattr(row, field.attname, value)
    row.currency_code = str(row.currency_code).upper()
    if (
        not re.fullmatch(r"[A-Z]{3}", row.currency_code)
        or row.currency_code not in settings.FUNDED_PROJECTS_CURRENCIES
    ):
        raise ValidationError(
            {"currency_code": "Use a configured institutional ISO currency code."}
        )
    row.full_clean(
        exclude=["staff_activity"], validate_unique=False, validate_constraints=False
    )
    if not row.project_title or not row.sanction_order_number:
        raise ValidationError("Project title and sanction order number are required.")
    if (
        row.principal_investigator_employee_id != row.staff_activity.employee_id
        or row.department_id != row.staff_activity.department_id
    ):
        raise ValidationError("PI and department must match the activity context.")
    if row.principal_investigator_employee.employment_status != "ACTIVE":
        raise ValidationError("The principal investigator must be active.")
    agency = row.funding_agency
    if (
        not agency.is_active
        or not agency.organization.is_active
        or not agency.funding_type.is_active
        or agency.funding_type_id != row.funding_type_id
    ):
        raise ValidationError("Select a matching active funding agency and type.")
    if row.sanction_date > row.project_start_date or (
        row.project_end_date and row.project_end_date < row.project_start_date
    ):
        raise ValidationError(
            "Sanction must precede project start; end must follow start."
        )
    if row.duration_months is not None and row.duration_months <= 0:
        raise ValidationError({"duration_months": "Use a positive planned duration."})
    if row.completion_date and row.completion_date < row.project_start_date:
        raise ValidationError({"completion_date": "Completion cannot precede start."})
    if not row.research_status.is_active:
        raise ValidationError("Project status must be active.")
    if (
        row.amount_received > row.sanctioned_amount
        or row.amount_utilized > row.amount_received
    ):
        raise ValidationError(
            "Received cannot exceed sanctioned; utilization cannot exceed receipts."
        )


def apply(row, values):
    allowed = {f.attname for f in row._meta.concrete_fields if not f.primary_key} - {
        "source_proposal_activity_id",
        "principal_investigator_employee_id",
        "department_id",
        "research_status_id",
        "amount_received",
        "amount_utilized",
    }
    if set(values) - allowed:
        raise ValidationError("Unknown or protected project field.")
    for key, value in values.items():
        setattr(row, key, value)


def dates(context):
    try:
        start = context["context_date"]
        end = start
        start = date.fromisoformat(start) if isinstance(start, str) else start
        end = date.fromisoformat(end) if isinstance(end, str) else end
        if not isinstance(start, date) or not isinstance(end, date) or end < start:
            raise ValueError()
        return start, end
    except (KeyError, TypeError, ValueError):
        raise ValidationError(
            {"context_date": "Supply the date used to select the PI assignment."}
        ) from None


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


@command
def save_activity(
    actor,
    values,
    *,
    context=None,
    activity_id=None,
    expected_version=None,
    key=None,
    source_id=None,
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
        if context or source_id:
            raise ValidationError("Project ownership and source are immutable.")
        row = FundedResearchProject.objects.get(pk=activity_id)
        if set(values) & (FINANCIAL_FIELDS | {"currency_code"}):
            require(actor, "FINANCE", "UPDATE", parent)
            require(actor, "FINANCE", "READ", parent)
        before = {k: str(getattr(row, k)) for k in values if hasattr(row, k)}
        if (
            "currency_code" in values
            and values["currency_code"] != row.currency_code
            and ResearchProjectFinancialUtilization.objects.filter(
                staff_activity=row
            ).exists()
        ):
            raise ValidationError(
                "Currency is immutable after financial reporting begins."
            )
        apply(row, values)
        normalize(row)
        for entry in ResearchProjectFinancialUtilization.objects.filter(
            staff_activity=row, void_record__isnull=True
        ):
            if entry.reporting_period_from < row.project_start_date or (
                row.project_end_date
                and entry.reporting_period_to > row.project_end_date
            ):
                raise ValidationError(
                    "Project dates must continue to include all active utilization periods."
                )
        reason = required_reason(reason)
        parent.activity_title = row.project_title
        parent.updated_by_user = actor
        parent.save()
        row.save()
        audit(
            actor,
            parent,
            "UPDATE",
            before,
            {k: str(getattr(row, k)) for k in values},
            reason,
            request_id,
        )
        return row
    if set(context) - {"employee_assignment_id", "academic_year_id", "context_date"}:
        raise ValidationError("Unknown or protected parent context.")

    def create():
        start, _ = dates(context)
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
                "Select an active PI assignment valid on the context date."
            )
        parent = StaffActivity(
            employee=assignment.employee,
            institution_id=assignment.employee.institution_id,
            campus_id=assignment.campus_id,
            department_id=assignment.department_id,
            activity_type=ActivityType.objects.get(
                activity_type_code=TYPE_CODE, activity_group="RESEARCH", is_active=True
            ),
            academic_year_id=context.get("academic_year_id"),
            start_date=start,
            approval_status=status(ApprovalStatus, "APPROVED"),
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
        row = FundedResearchProject(
            staff_activity=parent,
            principal_investigator_employee_id=parent.employee_id,
            department_id=parent.department_id,
            research_status=status(ResearchStatus, "SANCTIONED"),
        )
        if source_id:
            from apps.research_proposals.models import ResearchProposal
            from apps.research_proposals.permissions import require as proposal_require

            source_parent = StaffActivity.objects.select_for_update().get(
                pk=source_id, deleted_at__isnull=True
            )
            proposal_require(actor, "ACTIVITY", "READ", source_parent)
            from apps.staff_activities.specialization import ensure_exclusive

            ensure_exclusive(source_parent, ResearchProposal)
            if source_parent.activity_type.activity_type_code != "RESEARCH_PROPOSAL":
                raise ValidationError("Source activity is not a research proposal.")
            proposal = ResearchProposal.objects.get(pk=source_id)
            if (
                source_parent.approval_status.status_code != "APPROVED"
                or proposal.research_status.status_code != "APPROVED"
                or proposal.principal_investigator_employee_id != parent.employee_id
                or proposal.department_id != parent.department_id
            ):
                raise ValidationError(
                    "An approved proposal with the same PI and department is required."
                )
            if FundedResearchProject.objects.filter(
                source_proposal_activity_id=source_id
            ).exists():
                raise Conflict("This proposal already has a funded project.")
            row.source_proposal_activity = proposal
            row.project_title = proposal.proposal_title
            for field in (
                "funding_agency_id",
                "funding_type_id",
                "scheme_program_name",
                "requested_amount",
                "currency_code",
                "project_objectives",
                "research_domain",
            ):
                setattr(row, field, getattr(proposal, field))
        apply(row, values)
        normalize(row)
        parent.activity_title = row.project_title
        parent.full_clean(validate_unique=False, validate_constraints=False)
        parent.save()
        row.staff_activity = parent
        row.save()
        ProjectStatusHistory.objects.create(
            project=row,
            to_status=row.research_status,
            changed_by=actor,
            remarks="Funded award recorded",
        )
        audit(
            actor,
            parent,
            "CREATE",
            after={
                f.attname: str(getattr(row, f.attname))
                if getattr(row, f.attname) is not None
                else None
                for f in row._meta.concrete_fields
            },
            request_id=request_id,
        )
        return row

    return retry(
        actor,
        key,
        "project.create",
        {"context": context, "activity": values, "source": source_id},
        create,
        "CREATE",
    )


def required_reason(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
        raise ValidationError({"reason": "Supply a reason of 1-1000 characters."})
    return value.strip()


@command
def workflow(actor, pk, action, remarks, expected_version, key, request_id=None):
    if action not in TRANSITIONS:
        raise ValidationError("Unsupported project transition.")
    remarks = required_reason(remarks)

    def execute():
        fresh, parent = locked(actor, pk, "UPDATE", "STATUS")
        require(fresh, "ACTIVITY", "READ", parent)
        check_version(parent, expected_version)
        row = FundedResearchProject.objects.get(pk=pk)
        sources, target, _ = TRANSITIONS[action]
        if (
            not row.research_status.is_active
            or row.research_status.status_code not in sources
        ):
            raise ValidationError("Project transition is not allowed.")
        if action in {"complete", "close"} and (
            not row.completion_date or not row.project_outcomes
        ):
            raise ValidationError("Completion date and outcomes are required.")
        before = row.research_status
        row.research_status = status(ResearchStatus, target)
        row.save(update_fields=["research_status"])
        ProjectStatusHistory.objects.create(
            project=row,
            from_status=before,
            to_status=row.research_status,
            changed_by=fresh,
            remarks=remarks,
        )
        audit(
            fresh,
            parent,
            "UPDATE",
            {"status": before.status_code},
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
    if FundedResearchProject.objects.get(pk=pk).research_status.status_code not in {
        "CLOSED",
        "CANCELLED",
    }:
        raise ValidationError("Only closed or cancelled projects may be archived.")
    parent.deleted_at = timezone.now()
    parent.deleted_by_user = actor
    parent.save()
    audit(actor, parent, "DELETE")


def reconcile(row):
    from decimal import Decimal

    entries = ResearchProjectFinancialUtilization.objects.filter(
        staff_activity=row, void_record__isnull=True
    ).order_by("reporting_period_from", "pk")
    received = spent = balance = Decimal("0.00")
    previous = None
    for entry in entries:
        if previous and entry.reporting_period_from <= previous:
            raise ValidationError("Reporting periods cannot overlap.")
        if entry.opening_balance != balance:
            raise ValidationError(
                "Opening balance must equal the preceding closing balance (initially zero)."
            )
        if (
            entry.closing_balance
            != entry.opening_balance + entry.amount_received - entry.expenditure_amount
        ):
            raise ValidationError("Closing balance does not reconcile.")
        balance = entry.closing_balance
        received += entry.amount_received
        spent += entry.expenditure_amount
        previous = entry.reporting_period_to
    if received > row.sanctioned_amount or spent > received:
        raise ValidationError("Ledger totals exceed the sanctioned award or receipts.")
    row.amount_received = received
    row.amount_utilized = spent
    row.save(update_fields=["amount_received", "amount_utilized"])


@command
def utilization(
    actor,
    pk,
    values,
    *,
    expected_version,
    reason,
    key,
    utilization_id=None,
    void=False,
    request_id=None,
):
    reason = required_reason(reason)
    action = "DELETE" if void else "UPDATE"

    def execute():
        fresh, parent = locked(actor, pk, action, "FINANCE")
        require(fresh, "ACTIVITY", "READ", parent)
        require(fresh, "FINANCE", "READ", parent)
        check_version(parent, expected_version)
        editable(parent)
        project = FundedResearchProject.objects.get(pk=pk)
        entry = (
            ResearchProjectFinancialUtilization.objects.get(
                pk=utilization_id, staff_activity=project
            )
            if utilization_id
            else ResearchProjectFinancialUtilization(staff_activity=project)
        )
        if entry.pk and UtilizationVoid.objects.filter(utilization=entry).exists():
            raise ValidationError("Voided entries cannot be changed.")
        before = (
            {
                f.attname: str(getattr(entry, f.attname))
                for f in entry._meta.concrete_fields
            }
            if entry.pk
            else None
        )
        if void:
            if not entry.pk or values:
                raise ValidationError(
                    "Voiding requires an existing entry and no replacement values."
                )
            UtilizationVoid.objects.create(
                utilization=entry, actor=fresh, reason=reason
            )
        else:
            allowed = {
                f.attname for f in entry._meta.concrete_fields if not f.primary_key
            } - {"staff_activity_id", "created_at"}
            if set(values) - allowed:
                raise ValidationError("Unknown or protected utilization field.")
            for name, value in values.items():
                if isinstance(value, (float, bool)):
                    raise ValidationError("Use exact decimal strings for money.")
                setattr(entry, name, value)
            for name in (
                "utilization_certificate_number",
                "statement_of_expenditure_number",
            ):
                value = getattr(entry, name)
                if value is not None:
                    if not isinstance(value, str) or any(
                        ord(char) < 32 for char in value
                    ):
                        raise ValidationError(
                            {name: "Use a printable certificate identifier."}
                        )
                    setattr(entry, name, value.strip() or None)
            entry.full_clean(
                exclude=["created_at"],
                validate_unique=False,
                validate_constraints=False,
            )
            start, end = entry.reporting_period_from, entry.reporting_period_to
            if (
                not start
                or not end
                or end < start
                or start < project.project_start_date
                or (project.project_end_date and end > project.project_end_date)
            ):
                raise ValidationError(
                    "Supply a valid reporting period within the project dates."
                )
            match = re.fullmatch(r"([0-9]{4})-([0-9]{4})", entry.financial_year or "")
            if (
                not match
                or int(match[2]) != int(match[1]) + 1
                or start.year < int(match[1])
                or end.year > int(match[2])
            ):
                raise ValidationError(
                    {
                        "financial_year": "Use adjacent years YYYY-YYYY containing the reporting period."
                    }
                )
            for name in (
                "opening_balance",
                "amount_received",
                "expenditure_amount",
                "closing_balance",
            ):
                value = getattr(entry, name)
                if not value.is_finite() or value < 0:
                    raise ValidationError({name: "Use a nonnegative finite amount."})
            entry.save()
        reconcile(project)
        entry.refresh_from_db()
        after = {
            f.attname: str(getattr(entry, f.attname))
            for f in entry._meta.concrete_fields
        }
        after["void"] = void
        audit(fresh, parent, action, before, after, reason, request_id)
        return project

    return retry(
        actor,
        key,
        "project.utilization." + action,
        {
            "pk": str(pk),
            "entry": str(utilization_id),
            "values": values,
            "reason": reason,
            "version": expected_version,
        },
        execute,
        action,
        "FINANCE",
    )


def upload_attachment(
    *, actor, pk, expected_version, upload, title, category, replaces=None
):
    from apps.documents_exit.sharing import upload_shared

    def authorize(fresh):
        fresh, parent = locked(fresh, pk, "UPDATE")
        require(fresh, "ACTIVITY", "READ", parent)
        editable(parent)
        require(fresh, "FINANCE", "READ", parent)
        require(fresh, "FINANCE", "UPDATE", parent)
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
        _, parent = locked(fresh, pk, "READ")
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
