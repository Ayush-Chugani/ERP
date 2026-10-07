import csv
import io

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DomainError
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.db.models.functions import ExtractYear
from django.http import FileResponse, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class ProjectThrottle(UserRateThrottle):
    scope = "funded_projects"


from apps.conferences.api import IdentifierRead, PrivateResponse, StrictInput, writer
from apps.core.pagination import BoundedPagination
from apps.identity_access.audit import record
from apps.identity_access.models import ActivityAudit
from apps.organization.bulk import safe_cell
from apps.people_master.models import AccountLink, EmployeeAssignment
from apps.staff_activities.models import ActivityAttachment, StaffActivity
from apps.staff_profile import models as refs

from . import services as s
from .models import (
    FundedResearchProject,
    ProjectStatusHistory,
    ResearchProjectFinancialUtilization,
)
from .permissions import activity_scope, principal, require
from .services import TRANSITIONS

ProjectFields = writer(FundedResearchProject, "ProjectFields")


class ProjectMoney(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, float):
            raise ValidationError("Send monetary amounts as decimal strings.")
        return super().to_internal_value(data)


class ProjectWrite(ProjectFields):
    sanctioned_amount = ProjectMoney(
        max_digits=16, decimal_places=2, min_value=0, required=False
    )
    requested_amount = ProjectMoney(
        max_digits=16, decimal_places=2, required=False, allow_null=True, min_value=0
    )

    def get_fields(self):
        fields = super().get_fields()
        for name in (
            "principal_investigator_employee_id",
            "department_id",
            "research_status_id",
            "source_proposal_activity_id",
            "amount_received",
            "amount_utilized",
        ):
            fields.pop(name, None)
        for name in ("project_title", "funding_agency_id", "funding_type_id"):
            fields[name].required = False
        return fields


class ProjectContext(StrictInput, serializers.Serializer):
    employee_assignment_id = serializers.IntegerField(min_value=1)
    academic_year_id = serializers.IntegerField(
        min_value=1, allow_null=True, required=False
    )
    context_date = serializers.DateField()


class ProjectSave(StrictInput, serializers.Serializer):
    context = ProjectContext(required=False)
    activity = ProjectWrite()
    version = serializers.CharField(required=False, max_length=64)
    reason = serializers.CharField(required=False, max_length=1000)
    source_id = serializers.IntegerField(required=False, min_value=1)


class ProjectWorkflow(StrictInput, serializers.Serializer):
    action = serializers.ChoiceField(choices=list(TRANSITIONS))
    remarks = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )
    version = serializers.CharField(max_length=64)


class ProjectArchive(StrictInput, serializers.Serializer):
    version = serializers.CharField(max_length=64)


class ProjectUpload(StrictInput, serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=s.CATEGORIES)
    version = serializers.CharField(max_length=64)
    replaces = serializers.IntegerField(required=False, min_value=1)

    # Multipart QueryDict is accepted without weakening unknown-field checks.
    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))


class ProjectHistoryRead(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    from_status = serializers.CharField(
        source="from_status.status_code", allow_null=True
    )
    to_status = serializers.CharField(source="to_status.status_code")
    changed_by_id = serializers.CharField(read_only=True)

    class Meta:
        model = ProjectStatusHistory
        fields = (
            "id",
            "from_status",
            "to_status",
            "changed_by_id",
            "changed_at",
            "remarks",
        )


class ProjectRead(IdentifierRead):
    created_by_user_id = serializers.CharField(
        source="staff_activity.created_by_user_id", allow_null=True
    )
    updated_by_user_id = serializers.CharField(
        source="staff_activity.updated_by_user_id", allow_null=True
    )
    created_at = serializers.DateTimeField(source="staff_activity.created_at")
    updated_at = serializers.DateTimeField(source="staff_activity.updated_at")
    employee_id = serializers.CharField(source="staff_activity.employee_id")
    employee_name = serializers.CharField(source="staff_activity.employee.display_name")
    department_name = serializers.CharField(source="department.department_name")
    institution_id = serializers.CharField(source="staff_activity.institution_id")
    campus_id = serializers.CharField(
        source="staff_activity.campus_id", allow_null=True
    )
    department_id = serializers.CharField(
        source="staff_activity.department_id", allow_null=True
    )
    academic_year_id = serializers.CharField(
        source="staff_activity.academic_year_id", allow_null=True
    )
    context_date = serializers.DateField(source="staff_activity.start_date")
    status = serializers.CharField(source="research_status.status_code")
    funding_agency_name = serializers.CharField(
        source="funding_agency.organization.organization_name", allow_null=True
    )
    funding_type_name = serializers.CharField(
        source="funding_type.funding_type_name", allow_null=True
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.finance_visible:
            data["remaining_sanctioned"] = str(
                instance.sanctioned_amount - instance.amount_utilized
            )
            data["cash_balance"] = str(
                instance.amount_received - instance.amount_utilized
            )
        else:
            for field in s.FINANCIAL_FIELDS:
                data.pop(field, None)
        return data

    class Meta:
        model = FundedResearchProject
        fields = "__all__"


def allowed(actor, resource, action, parent):
    try:
        require(actor, resource, action, parent)
        return True
    except PermissionDenied:
        return False


def invoke(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainError as error:
        raise ValidationError(
            error.message_dict if hasattr(error, "message_dict") else error.messages
        ) from None
    except ObjectDoesNotExist:
        raise NotFound() from None


def validated(cls, request, partial=False):
    obj = cls(data=request.data, partial=partial)
    obj.is_valid(raise_exception=True)
    return obj.validated_data


PROJECT_FILTERS = [
    OpenApiParameter(name, str, description=description)
    for name, description in {
        "search": "Title, reference, domain or funding agency text",
        "pi": "Principal investigator employee ID",
        "employee": "Canonical parent employee ID",
        "institution": "Institution ID",
        "campus": "Campus ID",
        "department": "Department ID",
        "academic_year": "Academic year ID",
        "funding_agency": "Funding agency ID",
        "funding_type": "Funding type ID",
        "status": "Configured research status code",
        "domain": "Research domain text",
        "date_from": "Sanction date on or after YYYY-MM-DD",
        "date_to": "Sanction date on or before YYYY-MM-DD",
        "project_from": "Project starts on or after YYYY-MM-DD",
        "project_to": "Project ends on or before YYYY-MM-DD",
        "currency": "Uppercase three-letter currency",
        "amount_min": "Minimum sanctioned amount, decimal string",
        "amount_max": "Maximum sanctioned amount, decimal string",
        "mine": "1 restricts to the linked PI",
        "ordering": "staff_activity_id, project_title, sanction_date, funding_agency__organization__organization_name; optional minus prefix",
        "page": "Page number",
        "page_size": "1-100 records",
    }.items()
]


UtilizationFields = writer(ResearchProjectFinancialUtilization, "UtilizationFields")


class UtilizationWrite(UtilizationFields):
    def get_fields(self):
        fields = super().get_fields()
        fields.pop("staff_activity_id", None)
        for name in (
            "opening_balance",
            "amount_received",
            "expenditure_amount",
            "closing_balance",
        ):
            fields[name] = ProjectMoney(
                max_digits=16, decimal_places=2, min_value=0, required=False
            )
        return fields


class UtilizationCommand(StrictInput, serializers.Serializer):
    values = UtilizationWrite(required=False)
    utilization_id = serializers.IntegerField(required=False, min_value=1)
    void = serializers.BooleanField(default=False)
    version = serializers.CharField(max_length=64)
    reason = serializers.CharField(max_length=1000)


class UtilizationRead(IdentifierRead):
    voided = serializers.SerializerMethodField()

    def get_voided(self, obj):
        return hasattr(obj, "void_record")

    class Meta:
        model = ResearchProjectFinancialUtilization
        fields = "__all__"


class FinancialAuditRead(serializers.ModelSerializer):
    activity_audit_id = serializers.CharField(source="pk", read_only=True)
    user_id = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = ActivityAudit
        fields = (
            "activity_audit_id",
            "user_id",
            "activity_at",
            "action_code",
            "before_values",
            "after_values",
            "details",
            "request_identifier",
        )


class ProjectViewSet(PrivateResponse, viewsets.GenericViewSet):
    throttle_classes = (ProjectThrottle,)
    serializer_class = ProjectRead
    pagination_class = BoundedPagination
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FundedResearchProject.objects.none()
        rows = (
            FundedResearchProject.objects.filter(
                staff_activity__deleted_at__isnull=True
            )
            .filter(activity_scope(self.request.user))
            .annotate(
                finance_visible=Exists(
                    FundedResearchProject.objects.filter(
                        activity_scope(self.request.user, resource="FINANCE"),
                        pk=OuterRef("pk"),
                    )
                )
            )
            .select_related(
                "staff_activity__employee",
                "staff_activity__approval_status",
                "staff_activity__verification_status",
                "funding_agency__organization",
                "funding_type",
                "department",
                "research_status",
            )
        )
        q = self.request.query_params
        for key, path in {
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "funding_agency": "funding_agency_id",
            "funding_type": "funding_type_id",
        }.items():
            if q.get(key):
                if not q[key].isascii() or not q[key].isdigit() or len(q[key]) > 20:
                    raise ValidationError({key: "Use a valid identifier."})
                rows = rows.filter(**{path: q[key]})
        if q.get("pi"):
            rows = rows.filter(
                principal_investigator_employee_id=serializers.IntegerField(
                    min_value=1
                ).run_validation(q["pi"])
            )
        if q.get("currency"):
            rows = rows.filter(
                currency_code=serializers.RegexField(r"^[A-Z]{3}$").run_validation(
                    q["currency"]
                )
            )
        for name, lookup in (("amount_min", "gte"), ("amount_max", "lte")):
            if q.get(name):
                amount = serializers.DecimalField(
                    max_digits=16, decimal_places=2, min_value=0
                ).run_validation(q[name])
                rows = rows.filter(
                    activity_scope(self.request.user, resource="FINANCE")
                ).filter(**{"sanctioned_amount__" + lookup: amount})
        if q.get("mine") == "1":
            rows = rows.filter(
                staff_activity__employee__accountlink__user=self.request.user
            )
        for key, path in {
            "domain": "research_domain__icontains",
            "status": "research_status__status_code",
        }.items():
            if q.get(key):
                rows = rows.filter(**{path: q[key][:250]})
        for key, path in {
            "date_from": "sanction_date__gte",
            "date_to": "sanction_date__lte",
            "project_from": "project_start_date__gte",
            "project_to": "project_end_date__lte",
        }.items():
            if q.get(key):
                rows = rows.filter(
                    **{path: serializers.DateField().run_validation(q[key])}
                )
        if q.get("search"):
            term = q["search"][:200]
            rows = rows.filter(
                Q(project_title__icontains=term)
                | Q(funding_agency__organization__organization_name__icontains=term)
                | Q(sanction_order_number__icontains=term)
                | Q(research_domain__icontains=term)
                | Q(scheme_program_name__icontains=term)
            )
        ordering = q.get("ordering", "-staff_activity_id")
        allowed = {
            "staff_activity_id",
            "project_title",
            "sanction_date",
            "funding_agency__organization__organization_name",
        }
        if ordering.lstrip("-") not in allowed:
            raise ValidationError({"ordering": "Unsupported sort field."})
        return rows.order_by(ordering, "pk")

    @transaction.atomic
    def detail_data(self, row):
        StaffActivity.objects.select_for_update().get(pk=row.pk)
        # Refresh after writes so native timestamp defaults are concrete values.
        row = self.get_queryset().filter(pk=row.pk).first()
        if row is None:
            raise NotFound()
        data = ProjectRead(row, context={"request": self.request}).data
        data["version"] = s.version(row.pk)
        parent = row.staff_activity
        permissions = {}
        for name in ("UPDATE", "DELETE", "VERIFY", "APPROVE", "EXPORT"):
            try:
                require(self.request.user, "ACTIVITY", name, parent)
                permissions[name] = True
            except PermissionDenied:
                permissions[name] = False
        data["actions"] = [
            name
            for name, (sources, _, _) in TRANSITIONS.items()
            if row.research_status.status_code in sources
            and allowed(self.request.user, "STATUS", "UPDATE", parent)
        ]
        data["can_edit"] = (
            permissions["UPDATE"] and row.research_status.status_code in s.EDITABLE
        )
        data["can_archive"] = permissions[
            "DELETE"
        ] and row.research_status.status_code in {"CLOSED", "CANCELLED"}
        data["can_finance_view"] = allowed(self.request.user, "FINANCE", "READ", parent)
        data["can_finance_edit"] = (
            data["can_finance_view"]
            and row.research_status.status_code in s.EDITABLE
            and allowed(self.request.user, "FINANCE", "UPDATE", parent)
        )
        data["can_finance_void"] = (
            data["can_finance_view"]
            and row.research_status.status_code in s.EDITABLE
            and allowed(self.request.user, "FINANCE", "DELETE", parent)
        )
        # M13 file confidentiality checks are also applied before returning metadata.
        from apps.documents_exit.sharing import inspect_shared

        evidence = []
        for link in ActivityAttachment.objects.filter(staff_activity=parent).order_by(
            "-pk"
        )[:100]:
            try:
                require(self.request.user, "FINANCE", "READ", parent)
                inspect_shared(
                    actor=self.request.user,
                    file_id=link.file_object_id,
                    institution_id=parent.institution_id,
                )
            except (NotFound, PermissionDenied):
                continue
            evidence.append(
                {
                    "id": str(link.pk),
                    "title": link.title,
                    "category": link.category,
                    "replaces": str(link.replaces_id) if link.replaces_id else None,
                }
            )
        data["evidence"] = evidence
        data["history"] = ProjectHistoryRead(
            ProjectStatusHistory.objects.filter(project=parent.pk)
            .select_related("from_status", "to_status")
            .order_by("changed_at", "pk")[:25],
            many=True,
        ).data
        data["verification_remarks"] = parent.verification_remarks
        data["approval_remarks"] = parent.approval_remarks
        data["rejection_reason"] = parent.rejection_reason
        return data

    @extend_schema(parameters=PROJECT_FILTERS)
    def list(self, request):
        return self.get_paginated_response(
            ProjectRead(
                self.paginate_queryset(self.get_queryset()),
                many=True,
                context={"request": request},
            ).data
        )

    def retrieve(self, request, pk=None):
        return Response(self.detail_data(self.get_object()))

    @extend_schema(
        request=ProjectSave,
        responses=ProjectRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    def create(self, request):
        data = validated(ProjectSave, request)
        row = invoke(
            s.save_activity,
            request.user,
            data["activity"],
            context=data.get("context"),
            key=request.headers.get("Idempotency-Key"),
            source_id=data.get("source_id"),
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(row), status=201)

    @extend_schema(request=ProjectSave, responses=ProjectRead)
    def partial_update(self, request, pk=None):
        self.get_object()
        data = validated(ProjectSave, request, partial=True)
        row = invoke(
            s.save_activity,
            request.user,
            data.get("activity", {}),
            context=data.get("context"),
            activity_id=pk,
            expected_version=data.get("version"),
            source_id=data.get("source_id"),
            reason=data.get("reason", ""),
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(row))

    @extend_schema(request=ProjectArchive, responses={204: None})
    def destroy(self, request, pk=None):
        self.get_object()
        data = validated(ProjectArchive, request)
        invoke(s.archive, request.user, pk, data["version"])
        return Response(status=204)

    @extend_schema(
        request=ProjectWorkflow,
        responses=ProjectRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    @action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        self.get_object()
        data = validated(ProjectWorkflow, request)
        row = invoke(
            s.workflow,
            request.user,
            pk,
            data["action"],
            data.get("remarks", ""),
            data["version"],
            request.headers.get("Idempotency-Key"),
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(row))

    @extend_schema(request=ProjectUpload, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        self.get_object()
        data = validated(ProjectUpload, request)
        link = invoke(
            s.upload_attachment,
            actor=request.user,
            pk=pk,
            expected_version=data["version"],
            upload=data["file"],
            title=data["title"],
            category=data["category"],
            replaces=data.get("replaces"),
        )
        return Response({"id": str(link.pk), "version": s.version(pk)}, status=201)

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(
        detail=True,
        methods=["get"],
        url_path=r"evidence/(?P<attachment_id>[0-9]+)/download",
    )
    def download(self, request, pk=None, attachment_id=None):
        self.get_object()
        stream, file = invoke(
            s.download_attachment,
            actor=request.user,
            pk=pk,
            attachment_id=attachment_id,
        )
        response = FileResponse(
            stream,
            as_attachment=True,
            filename=file.original_file_name,
            content_type=file.mime_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @extend_schema(request=UtilizationCommand, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get", "post"])
    def utilization(self, request, pk=None):
        row = self.get_object()
        require(request.user, "FINANCE", "READ", row.staff_activity)
        if request.method == "GET":
            rows = (
                ResearchProjectFinancialUtilization.objects.filter(staff_activity=row)
                .select_related("void_record")
                .order_by("reporting_period_from", "pk")
            )
            return self.get_paginated_response(
                UtilizationRead(self.paginate_queryset(rows), many=True).data
            )
        data = validated(UtilizationCommand, request)
        result = invoke(
            s.utilization,
            request.user,
            pk,
            data.get("values", {}),
            expected_version=data["version"],
            reason=data["reason"],
            key=request.headers.get("Idempotency-Key"),
            utilization_id=data.get("utilization_id"),
            void=data.get("void", False),
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(result))

    @extend_schema(responses=FinancialAuditRead(many=True))
    @action(detail=True, methods=["get"], url_path="financial-history")
    def financial_history(self, request, pk=None):
        row = self.get_object()
        require(request.user, "FINANCE", "READ", row.staff_activity)
        rows = ActivityAudit.objects.filter(
            module_code=s.MODULE, entity_name="staff_activity", entity_id=str(pk)
        ).order_by("-pk")
        return self.get_paginated_response(
            FinancialAuditRead(self.paginate_queryset(rows), many=True).data
        )

    @extend_schema(responses=ProjectHistoryRead(many=True))
    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        self.get_object()
        rows = (
            ProjectStatusHistory.objects.filter(project_id=pk)
            .select_related("from_status", "to_status")
            .order_by("changed_at", "pk")
        )
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(ProjectHistoryRead(page, many=True).data)

    def report_rows(self):
        return (
            self.get_queryset()
            .filter(activity_scope(self.request.user, "EXPORT"))
            .filter(activity_scope(self.request.user, resource="FINANCE"))
            .filter(activity_scope(self.request.user, "EXPORT", resource="FINANCE"))
        )

    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=PROJECT_FILTERS)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.report_rows().annotate(sanction_year=ExtractYear("sanction_date"))
        groups = {}
        truncated = []
        for name, field in {
            "sanction_year": "sanction_year",
            "academic_year": "staff_activity__academic_year_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "employee": "staff_activity__employee_id",
            "funding_agency": "funding_agency_id",
            "funding_type": "funding_type_id",
            "domain": "research_domain",
            "status": "research_status__status_code",
        }.items():
            values = list(
                rows.order_by()
                .values(field, "currency_code")
                .annotate(
                    count=Count("pk"),
                    sanctioned_total=Sum("sanctioned_amount"),
                    received_total=Sum("amount_received"),
                    utilized_total=Sum("amount_utilized"),
                    remaining_total=Sum(F("sanctioned_amount") - F("amount_utilized")),
                )
                .order_by(field)[:101]
            )
            if len(values) > 100:
                truncated.append(name)
            groups[name] = [
                {
                    **{
                        k: str(v) if k.endswith("_total") and v is not None else v
                        for k, v in value.items()
                    },
                    "sanctioned_total": str(value["sanctioned_total"])
                    if value["sanctioned_total"] is not None
                    else None,
                }
                for value in values[:100]
            ]
        amounts = list(
            rows.order_by()
            .values("currency_code")
            .annotate(
                amount=Sum("sanctioned_amount"),
                received=Sum("amount_received"),
                utilized=Sum("amount_utilized"),
                remaining=Sum(F("sanctioned_amount") - F("amount_utilized")),
            )
            .order_by("currency_code")
        )
        return Response(
            {
                "count": rows.count(),
                "groups": groups,
                "truncated_groups": truncated,
                "amounts_by_currency": [
                    {
                        **{
                            k: str(v) if v is not None else None
                            for k, v in value.items()
                        },
                        "amount": str(value["amount"])
                        if value["amount"] is not None
                        else None,
                    }
                    for value in amounts
                ],
                "scope": "READ and EXPORT intersection",
            }
        )

    @extend_schema(responses=OpenApiTypes.BINARY, parameters=PROJECT_FILTERS)
    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = self.report_rows()
        if rows.count() > 10000:
            raise ValidationError("Narrow the report to at most 10,000 records.")
        stream = io.StringIO()
        writer_ = csv.writer(stream)
        columns = [f.attname for f in FundedResearchProject._meta.concrete_fields]
        parent_columns = [
            "employee_id",
            "institution_id",
            "campus_id",
            "department_id",
            "academic_year_id",
            "start_date",
            "end_date",
        ]
        writer_.writerow(columns + parent_columns + ["duration_days", "status"])
        count = 0
        for row in rows.iterator(chunk_size=500):
            parent = row.staff_activity
            duration = (
                (parent.end_date - parent.start_date).days + 1
                if parent.start_date and parent.end_date
                else ""
            )
            writer_.writerow(
                [
                    safe_cell(value)
                    for value in [
                        *[getattr(row, col) for col in columns],
                        *[getattr(parent, col) for col in parent_columns],
                        duration,
                        row.research_status.status_code,
                    ]
                ]
            )
            count += 1
        record(
            actor=request.user,
            module=s.MODULE,
            action="EXPORT",
            details={"rows": count},
        )
        response = HttpResponse(
            stream.getvalue(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="funded-projects.csv"'
        return response


def assignment_scope(actor, operation):
    paths = {
        "INSTITUTION": "employee__institution_id",
        "CAMPUS": "campus_id",
        "DEPARTMENT": "department_id",
        "SELF": "employee__accountlink__user_id",
    }
    return (
        activity_scope(actor, operation, paths=paths)
        & activity_scope(actor, paths=paths)
        & activity_scope(actor, resource="FINANCE", paths=paths)
        & activity_scope(
            actor,
            "UPDATE" if operation == "CREATE" else "EXPORT",
            resource="FINANCE",
            paths=paths,
        )
    )


class LookupViewSet(PrivateResponse, viewsets.ViewSet):
    throttle_classes = (ProjectThrottle,)
    serializer_class = serializers.Serializer

    @extend_schema(
        operation_id="project_lookup_catalogue", responses=OpenApiTypes.OBJECT
    )
    def list(self, request):
        principal(request.user)
        assignments = EmployeeAssignment.objects.filter(
            assignment_scope(request.user, "CREATE")
        )
        # Lookup availability requires an effective business scope.
        readable = FundedResearchProject.objects.filter(
            activity_scope(request.user)
        ).exists()
        if not assignments.exists() and not readable:
            raise PermissionDenied()
        return Response(
            {
                "can_create": assignments.exists(),
                "can_export": EmployeeAssignment.objects.filter(
                    assignment_scope(request.user, "EXPORT")
                ).exists(),
                "default_mine": AccountLink.objects.filter(
                    user=request.user, employee__isnull=False
                ).exists(),
                "categories": s.CATEGORIES,
            }
        )

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("id", str, OpenApiParameter.PATH)],
    )
    def retrieve(self, request, pk=None):
        self.list(request)
        search = request.query_params.get("search", "")[:200]
        from apps.academic_calendar.models import AcademicYear

        if pk == "proposal-prefill":
            from apps.research_proposals.models import ResearchProposal
            from apps.research_proposals.permissions import (
                activity_scope as proposal_scope,
            )

            source_id = serializers.IntegerField(min_value=1).run_validation(
                request.query_params.get("source_id")
            )
            source = (
                ResearchProposal.objects.filter(
                    proposal_scope(request.user),
                    pk=source_id,
                    staff_activity__deleted_at__isnull=True,
                    research_status__status_code="APPROVED",
                    staff_activity__approval_status__status_code="APPROVED",
                )
                .select_related("staff_activity")
                .first()
            )
            if source is None:
                raise NotFound()
            for resource, operation in [
                ("ACTIVITY", "CREATE"),
                ("FINANCE", "READ"),
                ("FINANCE", "UPDATE"),
            ]:
                require(request.user, resource, operation, source.staff_activity)
            values = {
                name: str(getattr(source, name))
                if getattr(source, name) is not None
                else None
                for name in (
                    "funding_agency_id",
                    "funding_type_id",
                    "scheme_program_name",
                    "requested_amount",
                    "currency_code",
                    "project_objectives",
                    "research_domain",
                )
            }
            values["project_title"] = source.proposal_title
            return Response(values)
        if pk == "assignments":
            rows = (
                EmployeeAssignment.objects.filter(
                    assignment_scope(request.user, "CREATE")
                )
                .select_related("employee", "campus", "department")
                .filter(
                    employee__display_name__icontains=search,
                    employee__employment_status="ACTIVE",
                    department__isnull=False,
                )
                .order_by("pk")
            )
            label = lambda row: (
                f"{row.employee.display_name} ? {row.campus.campus_name} / {row.department.department_name} ({row.start_date} ? {row.end_date or 'ongoing'})"
            )
        elif pk in {"funding_agencies", "funding_types", "statuses", "years"}:
            model, field = {
                "funding_agencies": (
                    refs.FundingAgency,
                    "organization__organization_name",
                ),
                "funding_types": (refs.FundingType, "funding_type_name"),
                "statuses": (refs.ResearchStatus, "status_name"),
                "years": (AcademicYear, "year_code"),
            }[pk]
            rows = model.objects.filter(**{field + "__icontains": search}).order_by(
                field, "pk"
            )
            if pk != "years":
                rows = rows.filter(is_active=True)
            if pk == "statuses":
                rows = rows.filter(
                    status_code__in=[
                        "SANCTIONED",
                        "ONGOING",
                        "COMPLETED",
                        "CLOSED",
                        "CANCELLED",
                    ]
                )
            if pk == "funding_agencies":
                rows = rows.filter(
                    organization__is_active=True, funding_type__is_active=True
                ).select_related("organization")
            label = lambda row: (
                row.organization.organization_name
                if pk == "funding_agencies"
                else getattr(row, field)
            )
        elif pk == "proposals":
            from apps.research_proposals.models import ResearchProposal
            from apps.research_proposals.permissions import (
                activity_scope as proposal_scope,
            )

            rows = ResearchProposal.objects.filter(
                proposal_scope(request.user),
                staff_activity__deleted_at__isnull=True,
                research_status__status_code="APPROVED",
                proposal_title__icontains=search,
            ).order_by("pk")
            label = lambda row: row.proposal_title
        elif pk == "domains":
            rows = (
                FundedResearchProject.objects.filter(
                    activity_scope(request.user),
                    staff_activity__deleted_at__isnull=True,
                    research_domain__icontains=search,
                )
                .exclude(research_domain__isnull=True)
                .exclude(research_domain="")
                .values_list("research_domain", flat=True)
                .order_by("research_domain")
                .distinct()
            )
            pagination = BoundedPagination()
            page = pagination.paginate_queryset(rows, request)
            return pagination.get_paginated_response(
                [{"id": value, "label": value} for value in page]
            )
        else:
            raise NotFound()
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [{"id": str(row.pk), "label": label(row)} for row in page]
        )
