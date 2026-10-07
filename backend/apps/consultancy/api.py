import csv
import io
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.conferences.api import IdentifierRead, PrivateResponse, StrictInput, writer
from apps.core.pagination import BoundedPagination
from apps.funded_projects.api import invoke, validated
from apps.identity_access.models import ActivityAudit
from apps.organization.bulk import safe_cell
from apps.people_master.models import Employee, EmployeeAssignment
from apps.staff_activities.models import ActivityAttachment, StaffActivity
from apps.staff_profile.models import ExternalOrganization

from . import services as s
from .models import (
    ConsultancyProject,
    ProjectMilestone,
    ProjectReceipt,
    ProjectStatusHistory,
    ProjectTeam,
)
from .permissions import activity_scope, principal, require


class ConsultancyThrottle(UserRateThrottle):
    scope = "consultancy"


class Money(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, (float, bool)):
            raise ValidationError("Send money as exact decimal strings.")
        return super().to_internal_value(data)


class ConsultancyWrite(writer(ConsultancyProject, "ConsultancyFields")):
    consultancy_amount = Money(
        max_digits=16, decimal_places=2, min_value=0, required=False
    )
    faculty_incentive_share = Money(
        max_digits=16, decimal_places=2, min_value=0, required=False, allow_null=True
    )

    def get_fields(self):
        fields = super().get_fields()
        for name in ("principal_consultant_employee_id", "amount_received", "status"):
            fields.pop(name, None)
        return fields


class ConsultancyContext(StrictInput, serializers.Serializer):
    employee_assignment_id = serializers.IntegerField(min_value=1)
    academic_year_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    context_date = serializers.DateField()


class ConsultancySave(StrictInput, serializers.Serializer):
    activity = ConsultancyWrite()
    context = ConsultancyContext(required=False)
    version = serializers.CharField(max_length=64, required=False)
    reason = serializers.CharField(max_length=1000, required=False)


class ConsultancyWorkflow(StrictInput, serializers.Serializer):
    action = serializers.ChoiceField(choices=list(s.TRANSITIONS))
    remarks = serializers.CharField(max_length=1000)
    version = serializers.CharField(max_length=64)


class ConsultancyArchive(StrictInput, serializers.Serializer):
    version = serializers.CharField(max_length=64)


class ConsultancyUpload(StrictInput, serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=s.CATEGORIES)
    version = serializers.CharField(max_length=64)
    replaces = serializers.IntegerField(required=False, min_value=1)

    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))


class ConsultancyExtension(StrictInput, serializers.Serializer):
    values = serializers.DictField(required=False, default=dict)
    item_id = serializers.IntegerField(min_value=1, required=False)
    void = serializers.BooleanField(default=False)
    version = serializers.CharField(max_length=64)
    reason = serializers.CharField(max_length=1000)


def extension_writer(model):
    class Write(writer(model, "Consultancy" + model.__name__ + "Fields")):
        def get_fields(self):
            fields = super().get_fields()
            for name in ("project_id", "actor_id", "created_at"):
                fields.pop(name, None)
            if model is ProjectReceipt:
                fields["amount"] = Money(max_digits=16, decimal_places=2, min_value=0)
            return fields

    return Write


def allowed(actor, resource, operation, parent):
    try:
        require(actor, resource, operation, parent)
        return True
    except PermissionDenied:
        return False


class ConsultancyRead(IdentifierRead):
    employee_name = serializers.CharField(
        source="principal_consultant_employee.display_name"
    )
    department_name = serializers.CharField(
        source="staff_activity.department.department_name", allow_null=True
    )
    client_name = serializers.CharField(source="client_organization.organization_name")
    context_date = serializers.DateField(source="staff_activity.start_date")
    created_at = serializers.DateTimeField(source="staff_activity.created_at")
    updated_at = serializers.DateTimeField(source="staff_activity.updated_at")

    class Meta:
        model = ConsultancyProject
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.finance_visible:
            data.update(s.metrics(instance))
        else:
            for field in s.FINANCIAL_FIELDS:
                data.pop(field, None)
        return data


class ConsultancyHistoryRead(IdentifierRead):
    class Meta:
        model = ProjectStatusHistory
        fields = "__all__"


class ConsultancyTeamRead(IdentifierRead):
    employee_name = serializers.CharField(source="employee.display_name")

    class Meta:
        model = ProjectTeam
        fields = "__all__"


class ConsultancyMilestoneRead(IdentifierRead):
    overdue = serializers.SerializerMethodField()

    def get_overdue(self, row):
        return row.status == "PLANNED" and row.due_date < timezone.localdate()

    class Meta:
        model = ProjectMilestone
        fields = "__all__"


class ConsultancyReceiptRead(IdentifierRead):
    voided = serializers.SerializerMethodField()

    def get_voided(self, row):
        return hasattr(row, "void_record")

    class Meta:
        model = ProjectReceipt
        fields = "__all__"


class ConsultancyAuditRead(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    user_id = serializers.CharField(allow_null=True)

    class Meta:
        model = ActivityAudit
        fields = (
            "id",
            "user_id",
            "activity_at",
            "action_code",
            "before_values",
            "after_values",
            "details",
            "request_identifier",
        )


FILTERS = [
    OpenApiParameter(name, str, description=description)
    for name, description in {
        "search": "Title, business references, client or consultant name",
        "status": "Core project status",
        "consultancy_type": "Core consultancy type",
        "client": "Client organization ID",
        "principal": "Principal employee ID",
        "institution": "Institution ID",
        "department": "Department ID",
        "campus": "Campus ID",
        "academic_year": "Academic year ID",
        "date_from": "Project starts on or after YYYY-MM-DD",
        "date_to": "Project starts on or before YYYY-MM-DD",
        "ordering": "pk, consultancy_title, project_start_date, completion_date, status (optional - prefix)",
        "page": "Page number",
    }.items()
]


class ConsultancyViewSet(PrivateResponse, viewsets.GenericViewSet):
    serializer_class = ConsultancyRead
    throttle_classes = (ConsultancyThrottle,)
    pagination_class = BoundedPagination
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ConsultancyProject.objects.none()
        user = self.request.user
        q = self.request.query_params
        rows = (
            ConsultancyProject.objects.filter(staff_activity__deleted_at__isnull=True)
            .filter(activity_scope(user))
            .annotate(
                finance_visible=Exists(
                    ConsultancyProject.objects.filter(
                        activity_scope(user, resource="FINANCE"), pk=OuterRef("pk")
                    )
                )
            )
            .select_related(
                "staff_activity__department",
                "staff_activity__employee",
                "principal_consultant_employee",
                "client_organization",
            )
        )
        for key, field in {
            "client": "client_organization_id",
            "principal": "principal_consultant_employee_id",
            "institution": "staff_activity__institution_id",
            "department": "staff_activity__department_id",
            "campus": "staff_activity__campus_id",
            "academic_year": "staff_activity__academic_year_id",
        }.items():
            if q.get(key):
                rows = rows.filter(
                    **{
                        field: serializers.IntegerField(
                            min_value=1, max_value=18446744073709551615
                        ).run_validation(q[key])
                    }
                )
        for key, choices in [
            ("status", ConsultancyProject.Status.values),
            ("consultancy_type", ConsultancyProject.Type.values),
        ]:
            if q.get(key):
                rows = rows.filter(
                    **{
                        key: serializers.ChoiceField(choices=choices).run_validation(
                            q[key]
                        )
                    }
                )
        for key, field in [
            ("date_from", "project_start_date__gte"),
            ("date_to", "project_start_date__lte"),
        ]:
            if q.get(key):
                rows = rows.filter(
                    **{field: serializers.DateField().run_validation(q[key])}
                )
        if q.get("search"):
            term = q["search"][:200]
            condition = Q(pk__in=[])
            for field in (
                "consultancy_title",
                "work_order_number",
                "agreement_number",
                "purchase_order_number",
                "client_organization__organization_name",
                "principal_consultant_employee__display_name",
            ):
                condition |= Q(**{field + "__icontains": term})
            rows = rows.filter(condition)
        if q.get("mine") == "1":
            rows = rows.filter(staff_activity__employee__accountlink__user=user)
        ordering = q.get("ordering", "-pk")
        if ordering.lstrip("-") not in {
            "pk",
            "consultancy_title",
            "project_start_date",
            "completion_date",
            "status",
        }:
            raise ValidationError("Unsupported ordering.")
        return rows.order_by(ordering, "pk")

    @transaction.atomic
    def detail_data(self, row):
        StaffActivity.objects.select_for_update().get(pk=row.pk)
        row = self.get_queryset().filter(pk=row.pk).first()
        if row is None:
            raise NotFound()
        parent = row.staff_activity
        data = ConsultancyRead(row).data
        data["version"] = s.version(row.pk)
        data["actions"] = [
            name
            for name, (sources, _, _) in s.TRANSITIONS.items()
            if row.status in sources
            and allowed(self.request.user, "STATUS", "UPDATE", parent)
        ]
        data["can_edit"] = row.status in s.EDITABLE and allowed(
            self.request.user, "ACTIVITY", "UPDATE", parent
        )
        data["can_archive"] = row.status in {"CANCELLED", "CLOSED"} and allowed(
            self.request.user, "ACTIVITY", "DELETE", parent
        )
        for key, resource in [
            ("finance", "FINANCE"),
            ("team", "TEAM"),
            ("milestone", "MILESTONE"),
            ("document", "DOCUMENT"),
        ]:
            data["can_" + key + "_view"] = allowed(
                self.request.user, resource, "READ", parent
            )
            data["can_" + key + "_edit"] = (
                (row.status in s.EDITABLE or key in {"finance", "document"})
                and data["can_" + key + "_view"]
                and allowed(self.request.user, resource, "UPDATE", parent)
            )
        data["can_finance_void"] = data["can_finance_view"] and allowed(
            self.request.user, "FINANCE", "DELETE", parent
        )
        data["history"] = ConsultancyHistoryRead(
            ProjectStatusHistory.objects.filter(project=row).order_by("pk")[:25],
            many=True,
        ).data
        from apps.documents_exit.sharing import inspect_shared

        links = []
        if data["can_document_view"]:
            for link in ActivityAttachment.objects.filter(
                staff_activity=parent
            ).order_by("-pk")[:100]:
                if (
                    link.category in s.FINANCIAL_DOCUMENTS
                    and not data["can_finance_view"]
                ):
                    continue
                try:
                    inspect_shared(
                        actor=self.request.user,
                        file_id=link.file_object_id,
                        institution_id=parent.institution_id,
                    )
                except (NotFound, PermissionDenied):
                    continue
                links.append(
                    {
                        "id": str(link.pk),
                        "title": link.title,
                        "category": link.category,
                        "replaces": str(link.replaces_id) if link.replaces_id else None,
                    }
                )
        data["evidence"] = links
        return data

    @extend_schema(parameters=FILTERS)
    def list(self, request):
        return self.get_paginated_response(
            ConsultancyRead(self.paginate_queryset(self.get_queryset()), many=True).data
        )

    def retrieve(self, request, pk=None):
        return Response(self.detail_data(self.get_object()))

    @extend_schema(request=ConsultancySave, responses=ConsultancyRead)
    def create(self, request):
        d = validated(ConsultancySave, request)
        row = invoke(
            s.save_activity,
            request.user,
            d["activity"],
            context=d.get("context"),
            key=request.headers.get("Idempotency-Key"),
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(row), status=201)

    @extend_schema(request=ConsultancySave, responses=ConsultancyRead)
    def partial_update(self, request, pk=None):
        self.get_object()
        d = validated(ConsultancySave, request, partial=True)
        row = invoke(
            s.save_activity,
            request.user,
            d.get("activity", {}),
            context=d.get("context"),
            activity_id=pk,
            expected_version=d.get("version"),
            reason=d.get("reason", ""),
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(row))

    @extend_schema(request=ConsultancyArchive, responses={204: None})
    def destroy(self, request, pk=None):
        self.get_object()
        d = validated(ConsultancyArchive, request)
        invoke(s.archive, request.user, pk, d["version"])
        return Response(status=204)

    @extend_schema(request=ConsultancyWorkflow, responses=ConsultancyRead)
    @action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        self.get_object()
        d = validated(ConsultancyWorkflow, request)
        return Response(
            self.detail_data(
                invoke(
                    s.workflow,
                    request.user,
                    pk,
                    d["action"],
                    d["remarks"],
                    d["version"],
                    request.headers.get("Idempotency-Key"),
                    request_id=request.headers.get("X-Request-ID", "")[:100],
                )
            )
        )

    @extend_schema(responses=ConsultancyHistoryRead(many=True))
    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        self.get_object()
        rows = ProjectStatusHistory.objects.filter(project_id=pk).order_by("pk")
        return self.get_paginated_response(
            ConsultancyHistoryRead(self.paginate_queryset(rows), many=True).data
        )

    @extend_schema(request=ConsultancyExtension, responses=OpenApiTypes.OBJECT)
    @action(
        detail=True,
        methods=["get", "post"],
        url_path=r"extensions/(?P<kind>team|milestones|receipts)",
    )
    def extensions(self, request, pk=None, kind=None):
        row = self.get_object()
        model, resource, reader = {
            "team": (ProjectTeam, "TEAM", ConsultancyTeamRead),
            "milestones": (ProjectMilestone, "MILESTONE", ConsultancyMilestoneRead),
            "receipts": (ProjectReceipt, "FINANCE", ConsultancyReceiptRead),
        }[kind]
        require(request.user, resource, "READ", row.staff_activity)
        if request.method == "GET":
            rows = model.objects.filter(project=row).order_by("pk")
            if kind == "team":
                rows = rows.select_related("employee")
            if kind == "receipts":
                rows = rows.select_related("void_record")
            response = self.get_paginated_response(
                reader(self.paginate_queryset(rows), many=True).data
            )
            if kind == "milestones":
                counts = rows.aggregate(
                    total=Count("pk", filter=~Q(status="CANCELLED")),
                    completed=Count(
                        "pk", filter=Q(status__in=["COMPLETED", "ACCEPTED"])
                    ),
                    overdue=Count(
                        "pk",
                        filter=Q(status="PLANNED", due_date__lt=timezone.localdate()),
                    ),
                )
                response.data["progress"] = {
                    **counts,
                    "percentage": str(
                        (Decimal(counts["completed"]) / counts["total"] * 100).quantize(
                            Decimal("0.01")
                        )
                    )
                    if counts["total"]
                    else None,
                }
            return response
        d = validated(ConsultancyExtension, request)
        values = d["values"]
        if not d["void"]:
            serializer = extension_writer(model)(
                data=values, partial=bool(d.get("item_id"))
            )
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
        result = invoke(
            s.extension,
            request.user,
            pk,
            kind,
            values,
            expected_version=d["version"],
            reason=d["reason"],
            key=request.headers.get("Idempotency-Key"),
            item_id=d.get("item_id"),
            void=d["void"],
            request_id=request.headers.get("X-Request-ID", "")[:100],
        )
        return Response(self.detail_data(result))

    @extend_schema(request=ConsultancyUpload, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        self.get_object()
        d = validated(ConsultancyUpload, request)
        link = invoke(
            s.upload_attachment,
            actor=request.user,
            pk=pk,
            expected_version=d["version"],
            upload=d["file"],
            title=d["title"],
            category=d["category"],
            replaces=d.get("replaces"),
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

    @extend_schema(responses=ConsultancyAuditRead(many=True))
    @action(detail=True, methods=["get"], url_path="financial-history")
    def financial_history(self, request, pk=None):
        row = self.get_object()
        require(request.user, "FINANCE", "READ", row.staff_activity)
        rows = ActivityAudit.objects.filter(
            module_code=s.MODULE, entity_name="staff_activity", entity_id=str(pk)
        ).order_by("-pk")
        return self.get_paginated_response(
            ConsultancyAuditRead(self.paginate_queryset(rows), many=True).data
        )

    def report_rows(self):
        user = self.request.user
        return self.get_queryset().filter(
            activity_scope(user, "EXPORT"),
            activity_scope(user, resource="FINANCE"),
            activity_scope(user, "EXPORT", resource="FINANCE"),
        )

    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=FILTERS)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.report_rows()
        groups = {}
        for name, field in {
            "status": "status",
            "type": "consultancy_type",
            "client": "client_organization__organization_name",
            "department": "staff_activity__department__department_name",
            "institution": "staff_activity__institution_id",
        }.items():
            values = (
                rows.order_by()
                .values(field, "currency_code")
                .annotate(
                    count=Count("pk"),
                    consultancy_total=Sum("consultancy_amount"),
                    received_total=Sum("amount_received"),
                    balance_total=Sum(F("consultancy_amount") - F("amount_received")),
                )
                .order_by(field)[:101]
            )
            groups[name] = [
                {k: str(v) if isinstance(v, Decimal) else v for k, v in value.items()}
                for value in values
            ]
        return Response(
            {
                "count": rows.count(),
                "groups": groups,
                "group_limit": 101,
                "scope": "ACTIVITY READ/EXPORT and FINANCE READ/EXPORT intersection",
            }
        )

    @extend_schema(responses=OpenApiTypes.BINARY, parameters=FILTERS)
    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = self.report_rows()
        if rows.count() > 10000:
            raise ValidationError("Narrow export to 10,000 projects.")
        stream = io.StringIO()
        out = csv.writer(stream)
        columns = [f.attname for f in ConsultancyProject._meta.concrete_fields]
        out.writerow(
            columns
            + [
                "client_name",
                "consultant_name",
                "balance_receivable",
                "collection_percentage",
            ]
        )
        for row in rows.iterator(chunk_size=500):
            out.writerow(
                [
                    safe_cell(v)
                    for v in [
                        *[getattr(row, col) for col in columns],
                        row.client_organization.organization_name,
                        row.principal_consultant_employee.display_name,
                        *s.metrics(row).values(),
                    ]
                ]
            )
        s.audit(request.user, None, "EXPORT", after={"count": rows.count()})
        response = HttpResponse(
            stream.getvalue(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="consultancy.csv"'
        return response


def assignment_scope(actor):
    paths = {
        "INSTITUTION": "employee__institution_id",
        "CAMPUS": "campus_id",
        "DEPARTMENT": "department_id",
        "SELF": "employee__accountlink__user_id",
    }
    return (
        activity_scope(actor, "CREATE", paths=paths)
        & activity_scope(actor, paths=paths)
        & activity_scope(actor, "UPDATE", resource="FINANCE", paths=paths)
        & activity_scope(actor, resource="FINANCE", paths=paths)
    )


class ConsultancyLookupViewSet(PrivateResponse, viewsets.ViewSet):
    serializer_class = serializers.Serializer
    throttle_classes = (ConsultancyThrottle,)

    @extend_schema(
        operation_id="consultancy_lookup_catalogue", responses=OpenApiTypes.OBJECT
    )
    def list(self, request):
        principal(request.user)
        create = EmployeeAssignment.objects.filter(
            assignment_scope(request.user),
            employee__employment_status="ACTIVE",
            department__isnull=False,
        ).exists()
        readable = ConsultancyProject.objects.filter(
            activity_scope(request.user), staff_activity__deleted_at__isnull=True
        ).exists()
        if not create and not readable:
            raise PermissionDenied()
        return Response(
            {
                "can_create": create,
                "can_export": ConsultancyProject.objects.filter(
                    activity_scope(request.user, "EXPORT"),
                    activity_scope(request.user, resource="FINANCE"),
                    activity_scope(request.user, "EXPORT", resource="FINANCE"),
                ).exists(),
                "categories": s.CATEGORIES,
                "types": ConsultancyProject.Type.values,
                "statuses": ConsultancyProject.Status.values,
            }
        )

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("id", str, OpenApiParameter.PATH)],
    )
    def retrieve(self, request, pk=None):
        self.list(request)
        search = request.query_params.get("search", "")[:200]
        if pk == "assignments":
            rows = (
                EmployeeAssignment.objects.filter(
                    assignment_scope(request.user),
                    employee__employment_status="ACTIVE",
                    department__isnull=False,
                    employee__display_name__icontains=search,
                )
                .select_related("employee", "department", "campus")
                .order_by("pk")
            )
            label = lambda row: (
                f"{row.employee.display_name} / {row.department.department_name} / {row.campus.campus_name} ({row.start_date} - {row.end_date or 'ongoing'})"
            )
        elif pk == "clients":
            rows = ExternalOrganization.objects.filter(
                is_active=True, organization_name__icontains=search
            ).order_by("organization_name", "pk")
            label = lambda row: row.organization_name
        elif pk == "years":
            from apps.academic_calendar.models import AcademicYear

            rows = AcademicYear.objects.filter(year_code__icontains=search).order_by(
                "pk"
            )
            label = lambda row: row.year_code
        elif pk == "employees":
            project_id = serializers.IntegerField(min_value=1).run_validation(
                request.query_params.get("project_id")
            )
            project = (
                ConsultancyProject.objects.filter(
                    activity_scope(request.user),
                    pk=project_id,
                    staff_activity__deleted_at__isnull=True,
                )
                .select_related("staff_activity")
                .first()
            )
            if not project:
                raise NotFound()
            require(request.user, "TEAM", "UPDATE", project.staff_activity)
            require(request.user, "TEAM", "READ", project.staff_activity)
            rows = (
                Employee.objects.filter(
                    institution_id=project.staff_activity.institution_id,
                    employment_status="ACTIVE",
                    display_name__icontains=search,
                )
                .exclude(pk=project.principal_consultant_employee_id)
                .order_by("pk")
            )
            label = lambda row: row.display_name
        else:
            raise NotFound()
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [{"id": str(row.pk), "label": label(row)} for row in page]
        )
