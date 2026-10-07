import csv
import io

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DomainError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class InternshipThrottle(UserRateThrottle):
    scope = "faculty_internships"


from apps.conferences.api import IdentifierRead, PrivateResponse, StrictInput, writer
from apps.core.pagination import BoundedPagination
from apps.identity_access.audit import record
from apps.organization.bulk import safe_cell
from apps.people_master.models import AccountLink, EmployeeAssignment
from apps.staff_activities.models import ActivityAttachment, StaffActivity
from apps.staff_activities.workflow import TRANSITIONS
from apps.staff_profile import models as refs

from . import services as s
from .models import FacultyInternship
from .permissions import activity_scope, principal, require

InternshipWrite = writer(FacultyInternship, "InternshipWrite")


class InternshipContext(StrictInput, serializers.Serializer):
    employee_assignment_id = serializers.IntegerField(min_value=1)
    academic_year_id = serializers.IntegerField(
        min_value=1, allow_null=True, required=False
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class InternshipSave(StrictInput, serializers.Serializer):
    context = InternshipContext(required=False)
    activity = InternshipWrite()
    version = serializers.CharField(required=False, max_length=64)


class InternshipWorkflow(StrictInput, serializers.Serializer):
    action = serializers.ChoiceField(choices=list(TRANSITIONS))
    remarks = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )
    version = serializers.CharField(max_length=64)


class InternshipArchive(StrictInput, serializers.Serializer):
    version = serializers.CharField(max_length=64)


class InternshipUpload(StrictInput, serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=s.CATEGORIES)
    version = serializers.CharField(max_length=64)
    replaces = serializers.IntegerField(required=False, min_value=1)

    # Multipart QueryDict is accepted without weakening unknown-field checks.
    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))


class InternshipRead(IdentifierRead):
    employee_id = serializers.CharField(source="staff_activity.employee_id")
    employee_name = serializers.CharField(source="staff_activity.employee.display_name")
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
    start_date = serializers.DateField(source="staff_activity.start_date")
    end_date = serializers.DateField(source="staff_activity.end_date")
    status = serializers.CharField(source="staff_activity.approval_status.status_code")
    organization_name = serializers.CharField(source="organization.organization_name")
    sector_name = serializers.CharField(
        source="industry_sector.sector_name", allow_null=True
    )

    class Meta:
        model = FacultyInternship
        fields = "__all__"


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


class InternshipViewSet(PrivateResponse, viewsets.GenericViewSet):
    throttle_classes = (InternshipThrottle,)
    serializer_class = InternshipRead
    pagination_class = BoundedPagination
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FacultyInternship.objects.none()
        rows = (
            FacultyInternship.objects.filter(staff_activity__deleted_at__isnull=True)
            .filter(activity_scope(self.request.user))
            .select_related(
                "staff_activity__employee",
                "staff_activity__approval_status",
                "staff_activity__verification_status",
                "organization",
                "industry_sector",
            )
        )
        q = self.request.query_params
        for key, path in {
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "organization": "organization_id",
            "industry_sector": "industry_sector_id",
        }.items():
            if q.get(key):
                if not q[key].isascii() or not q[key].isdigit() or len(q[key]) > 20:
                    raise ValidationError({key: "Use a valid identifier."})
                rows = rows.filter(**{path: q[key]})
        if q.get("mine") == "1":
            rows = rows.filter(
                staff_activity__employee__accountlink__user=self.request.user
            )
        for key, path in {
            "domain": "internship_domain__icontains",
            "stipend_type": "stipend_incentive_type",
            "status": "staff_activity__approval_status__status_code",
        }.items():
            if q.get(key):
                rows = rows.filter(**{path: q[key][:250]})
        for key, path in {
            "date_from": "staff_activity__start_date__gte",
            "date_to": "staff_activity__end_date__lte",
        }.items():
            if q.get(key):
                rows = rows.filter(
                    **{path: serializers.DateField().run_validation(q[key])}
                )
        if q.get("search"):
            term = q["search"][:200]
            rows = rows.filter(
                Q(internship_title__icontains=term)
                | Q(organization__organization_name__icontains=term)
                | Q(mentor_name__icontains=term)
                | Q(internship_domain__icontains=term)
            )
        ordering = q.get("ordering", "-staff_activity_id")
        allowed = {
            "staff_activity_id",
            "internship_title",
            "staff_activity__start_date",
            "organization__organization_name",
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
        data = InternshipRead(row).data
        data["version"] = s.version(row.pk)
        parent = row.staff_activity
        permissions = {}
        for name in ("UPDATE", "DELETE", "VERIFY", "APPROVE", "EXPORT"):
            try:
                require(self.request.user, "ACTIVITY", name, parent)
                permissions[name] = True
            except PermissionDenied:
                permissions[name] = False
        independent = (
            parent.created_by_user_id != self.request.user.pk
            and not AccountLink.objects.filter(
                user=self.request.user, employee_id=parent.employee_id
            ).exists()
        )
        data["actions"] = [
            name
            for name, (sources, _, perm) in TRANSITIONS.items()
            if parent.approval_status.status_code in sources
            and permissions[perm]
            and (perm == "UPDATE" or independent)
        ]
        data["can_edit"] = (
            permissions["UPDATE"] and parent.approval_status.status_code in s.EDITABLE
        )
        data["can_archive"] = permissions[
            "DELETE"
        ] and parent.approval_status.status_code in {
            "DRAFT",
            "RETURNED",
            "WITHDRAWN",
            "REJECTED",
        }
        # M13 file confidentiality checks are also applied before returning metadata.
        from apps.documents_exit.sharing import inspect_shared

        evidence = []
        for link in ActivityAttachment.objects.filter(staff_activity=parent).order_by(
            "-pk"
        )[:100]:
            try:
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
        from apps.identity_access.models import ActivityAudit

        data["history"] = list(
            ActivityAudit.objects.filter(
                module_code=s.MODULE,
                entity_name="staff_activity",
                entity_id=str(parent.pk),
            )
            .order_by("-activity_at")
            .values("action_code", "activity_at", "before_values", "after_values")[:100]
        )
        data["verification_remarks"] = parent.verification_remarks
        data["approval_remarks"] = parent.approval_remarks
        data["rejection_reason"] = parent.rejection_reason
        return data

    def list(self, request):
        return self.get_paginated_response(
            InternshipRead(self.paginate_queryset(self.get_queryset()), many=True).data
        )

    def retrieve(self, request, pk=None):
        return Response(self.detail_data(self.get_object()))

    @extend_schema(
        request=InternshipSave,
        responses=InternshipRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    def create(self, request):
        data = validated(InternshipSave, request)
        row = invoke(
            s.save_activity,
            request.user,
            data["activity"],
            context=data.get("context"),
            key=request.headers.get("Idempotency-Key"),
        )
        return Response(self.detail_data(row), status=201)

    @extend_schema(request=InternshipSave, responses=InternshipRead)
    def partial_update(self, request, pk=None):
        self.get_object()
        data = validated(InternshipSave, request, partial=True)
        row = invoke(
            s.save_activity,
            request.user,
            data.get("activity", {}),
            context=data.get("context"),
            activity_id=pk,
            expected_version=data.get("version"),
        )
        return Response(self.detail_data(row))

    @extend_schema(request=InternshipArchive, responses={204: None})
    def destroy(self, request, pk=None):
        self.get_object()
        data = validated(InternshipArchive, request)
        invoke(s.archive, request.user, pk, data["version"])
        return Response(status=204)

    @extend_schema(
        request=InternshipWorkflow,
        responses=InternshipRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    @action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        self.get_object()
        data = validated(InternshipWorkflow, request)
        row = invoke(
            s.workflow,
            request.user,
            pk,
            data["action"],
            data.get("remarks", ""),
            data["version"],
            request.headers.get("Idempotency-Key"),
        )
        return Response(self.detail_data(row))

    @extend_schema(request=InternshipUpload, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        self.get_object()
        data = validated(InternshipUpload, request)
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

    def report_rows(self):
        return self.get_queryset().filter(activity_scope(self.request.user, "EXPORT"))

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.report_rows()
        groups = {}
        truncated = []
        for name, field in {
            "academic_year": "staff_activity__academic_year_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "employee": "staff_activity__employee_id",
            "organization": "organization_id",
            "sector": "industry_sector_id",
            "domain": "internship_domain",
            "stipend_type": "stipend_incentive_type",
            "status": "staff_activity__approval_status__status_code",
        }.items():
            values = list(
                rows.order_by()
                .values(field)
                .annotate(count=Count("pk"))
                .order_by(field)[:101]
            )
            if len(values) > 100:
                truncated.append(name)
            groups[name] = values[:100]
        amounts = list(
            rows.order_by()
            .values("currency_code")
            .annotate(amount=Sum("stipend_incentive_amount"))
            .order_by("currency_code")
        )
        return Response(
            {
                "count": rows.count(),
                "groups": groups,
                "truncated_groups": truncated,
                "amounts_by_currency": amounts,
                "scope": "READ and EXPORT intersection",
            }
        )

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = self.report_rows()
        if rows.count() > 10000:
            raise ValidationError("Narrow the report to at most 10,000 records.")
        stream = io.StringIO()
        writer_ = csv.writer(stream)
        columns = [f.attname for f in FacultyInternship._meta.concrete_fields]
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
                        parent.approval_status.status_code,
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
        response["Content-Disposition"] = (
            'attachment; filename="faculty-internships.csv"'
        )
        return response


class LookupViewSet(PrivateResponse, viewsets.ViewSet):
    throttle_classes = (InternshipThrottle,)
    serializer_class = serializers.Serializer

    @extend_schema(
        operation_id="internship_lookup_catalogue", responses=OpenApiTypes.OBJECT
    )
    def list(self, request):
        principal(request.user)
        assignments = EmployeeAssignment.objects.filter(
            activity_scope(
                request.user,
                "CREATE",
                paths={
                    "INSTITUTION": "employee__institution_id",
                    "CAMPUS": "campus_id",
                    "DEPARTMENT": "department_id",
                    "SELF": "employee__accountlink__user_id",
                },
            )
        )
        # Lookup availability requires an effective business scope.
        readable = FacultyInternship.objects.filter(
            activity_scope(request.user)
        ).exists()
        if not assignments.exists() and not readable:
            raise PermissionDenied()
        return Response(
            {
                "can_create": assignments.exists(),
                "can_export": EmployeeAssignment.objects.filter(
                    activity_scope(
                        request.user,
                        "EXPORT",
                        paths={
                            "INSTITUTION": "employee__institution_id",
                            "CAMPUS": "campus_id",
                            "DEPARTMENT": "department_id",
                            "SELF": "employee__accountlink__user_id",
                        },
                    )
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

        if pk == "assignments":
            rows = (
                EmployeeAssignment.objects.filter(
                    activity_scope(
                        request.user,
                        "CREATE",
                        paths={
                            "INSTITUTION": "employee__institution_id",
                            "CAMPUS": "campus_id",
                            "DEPARTMENT": "department_id",
                            "SELF": "employee__accountlink__user_id",
                        },
                    )
                )
                .select_related("employee", "campus")
                .filter(employee__display_name__icontains=search)
                .order_by("pk")
            )
            label = lambda row: (
                f"{row.employee.display_name} ? {row.campus.campus_name} ({row.start_date} ? {row.end_date or 'ongoing'})"
            )
        elif pk in {"organizations", "sectors", "years"}:
            model, field = {
                "organizations": (refs.ExternalOrganization, "organization_name"),
                "sectors": (refs.IndustrySector, "sector_name"),
                "years": (AcademicYear, "year_code"),
            }[pk]
            rows = model.objects.filter(**{field + "__icontains": search}).order_by(
                field, "pk"
            )
            if pk != "years":
                rows = rows.filter(is_active=True)
            label = lambda row: getattr(row, field)
        else:
            raise NotFound()
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [{"id": str(row.pk), "label": label(row)} for row in page]
        )
