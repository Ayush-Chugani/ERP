import csv
import io

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DomainError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class CocurricularThrottle(UserRateThrottle):
    scope = "cocurricular"


from apps.conferences.api import IdentifierRead, PrivateResponse, StrictInput, writer
from apps.core.pagination import BoundedPagination
from apps.identity_access.audit import record
from apps.organization.bulk import safe_cell
from apps.people_master.models import AccountLink, EmployeeAssignment
from apps.staff_activities.models import ActivityAttachment, StaffActivity
from apps.staff_activities.workflow import TRANSITIONS
from apps.staff_profile import models as refs

from . import services as s
from .models import CocurricularActivity, CocurricularStatusHistory
from .permissions import activity_scope, principal, require

CocurricularFields = writer(CocurricularActivity, "CocurricularFields")


CocurricularWrite = CocurricularFields


class CocurricularContext(StrictInput, serializers.Serializer):
    employee_assignment_id = serializers.IntegerField(min_value=1)
    academic_year_id = serializers.IntegerField(
        min_value=1, allow_null=True, required=False
    )
    context_date = serializers.DateField()


class CocurricularSave(StrictInput, serializers.Serializer):
    context = CocurricularContext(required=False)
    activity = CocurricularWrite()
    version = serializers.CharField(required=False, max_length=64)


class CocurricularWorkflow(StrictInput, serializers.Serializer):
    action = serializers.ChoiceField(choices=list(TRANSITIONS))
    remarks = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )
    version = serializers.CharField(max_length=64)


class CocurricularArchive(StrictInput, serializers.Serializer):
    version = serializers.CharField(max_length=64)


class CocurricularUpload(StrictInput, serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=s.CATEGORIES)
    version = serializers.CharField(max_length=64)
    replaces = serializers.IntegerField(required=False, min_value=1)

    # Multipart QueryDict is accepted without weakening unknown-field checks.
    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))


class CocurricularHistoryRead(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    from_status = serializers.CharField(
        source="from_status.status_code", allow_null=True
    )
    to_status = serializers.CharField(source="to_status.status_code")
    changed_by_id = serializers.CharField(read_only=True)

    class Meta:
        model = CocurricularStatusHistory
        fields = (
            "id",
            "from_status",
            "to_status",
            "changed_by_id",
            "changed_at",
            "remarks",
        )


class CocurricularRead(IdentifierRead):
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
    department_name = serializers.CharField(
        source="staff_activity.department.department_name", allow_null=True
    )
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
    status = serializers.CharField(source="staff_activity.approval_status.status_code")
    category_name = serializers.CharField(source="cocurricular_category.category_name")
    organizer_name = serializers.CharField(
        source="organizer.organization.organization_name", allow_null=True
    )
    institution_organization_name = serializers.CharField(
        source="institution_organization.organization_name", allow_null=True
    )
    country_name = serializers.CharField(source="country.country_name", allow_null=True)
    state_name = serializers.CharField(source="state.state_name", allow_null=True)

    class Meta:
        model = CocurricularActivity
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


ACTIVITY_FILTERS = [
    OpenApiParameter(name, str)
    for name in (
        "search",
        "employee",
        "institution",
        "campus",
        "department",
        "academic_year",
        "category",
        "organizer",
        "institution_organization",
        "country",
        "state",
        "city",
        "achievement",
        "status",
        "date_from",
        "date_to",
        "mine",
        "ordering",
        "page",
        "page_size",
    )
]


class CocurricularViewSet(PrivateResponse, viewsets.GenericViewSet):
    throttle_classes = (CocurricularThrottle,)
    serializer_class = CocurricularRead
    pagination_class = BoundedPagination
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CocurricularActivity.objects.none()
        rows = (
            CocurricularActivity.objects.filter(staff_activity__deleted_at__isnull=True)
            .filter(activity_scope(self.request.user))
            .select_related(
                "staff_activity__employee",
                "staff_activity__approval_status",
                "staff_activity__verification_status",
                "staff_activity__department",
                "cocurricular_category",
                "organizer__organization",
                "institution_organization",
                "country",
                "state",
            )
        )
        q = self.request.query_params
        for key, path in {
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "category": "cocurricular_category_id",
            "organizer": "organizer_id",
            "institution_organization": "institution_organization_id",
            "country": "country_id",
            "state": "state_id",
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
            "city": "city__icontains",
            "achievement": "achievement_award__icontains",
            "status": "staff_activity__approval_status__status_code",
        }.items():
            if q.get(key):
                rows = rows.filter(**{path: q[key][:250]})
        for key, path in {
            "date_from": "event_date__gte",
            "date_to": "event_date__lte",
        }.items():
            if q.get(key):
                rows = rows.filter(
                    **{path: serializers.DateField().run_validation(q[key])}
                )
        if q.get("search"):
            term = q["search"][:200]
            rows = rows.filter(
                Q(event_name__icontains=term)
                | Q(organizer__organization__organization_name__icontains=term)
                | Q(achievement_award__icontains=term)
                | Q(institution_organization__organization_name__icontains=term)
            )
        ordering = q.get("ordering", "-staff_activity_id")
        allowed = {
            "staff_activity_id",
            "event_name",
            "event_date",
            "cocurricular_category__category_name",
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
        data = CocurricularRead(row).data
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
        data["history"] = CocurricularHistoryRead(
            CocurricularStatusHistory.objects.filter(activity=parent.pk)
            .select_related("from_status", "to_status")
            .order_by("changed_at", "pk")[:25],
            many=True,
        ).data
        data["verification_remarks"] = parent.verification_remarks
        data["approval_remarks"] = parent.approval_remarks
        data["rejection_reason"] = parent.rejection_reason
        return data

    @extend_schema(parameters=ACTIVITY_FILTERS)
    def list(self, request):
        return self.get_paginated_response(
            CocurricularRead(
                self.paginate_queryset(self.get_queryset()), many=True
            ).data
        )

    def retrieve(self, request, pk=None):
        return Response(self.detail_data(self.get_object()))

    @extend_schema(
        request=CocurricularSave,
        responses=CocurricularRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    def create(self, request):
        data = validated(CocurricularSave, request)
        row = invoke(
            s.save_activity,
            request.user,
            data["activity"],
            context=data.get("context"),
            key=request.headers.get("Idempotency-Key"),
        )
        return Response(self.detail_data(row), status=201)

    @extend_schema(request=CocurricularSave, responses=CocurricularRead)
    def partial_update(self, request, pk=None):
        self.get_object()
        data = validated(CocurricularSave, request, partial=True)
        row = invoke(
            s.save_activity,
            request.user,
            data.get("activity", {}),
            context=data.get("context"),
            activity_id=pk,
            expected_version=data.get("version"),
        )
        return Response(self.detail_data(row))

    @extend_schema(request=CocurricularArchive, responses={204: None})
    def destroy(self, request, pk=None):
        self.get_object()
        data = validated(CocurricularArchive, request)
        invoke(s.archive, request.user, pk, data["version"])
        return Response(status=204)

    @extend_schema(
        request=CocurricularWorkflow,
        responses=CocurricularRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    @action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        self.get_object()
        data = validated(CocurricularWorkflow, request)
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

    @extend_schema(request=CocurricularUpload, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        self.get_object()
        data = validated(CocurricularUpload, request)
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

    @extend_schema(responses=CocurricularHistoryRead(many=True))
    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        self.get_object()
        rows = (
            CocurricularStatusHistory.objects.filter(activity_id=pk)
            .select_related("from_status", "to_status")
            .order_by("changed_at", "pk")
        )
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(
            CocurricularHistoryRead(page, many=True).data
        )

    def report_rows(self):
        return self.get_queryset().filter(activity_scope(self.request.user, "EXPORT"))

    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=ACTIVITY_FILTERS)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.report_rows()
        groups, truncated = {}, []
        for name, field in {
            "category": "cocurricular_category__category_name",
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "organizer": "organizer__organization__organization_name",
            "organization": "institution_organization__organization_name",
            "country": "country__country_name",
            "state": "state__state_name",
            "city": "city",
            "event": "event_name",
            "event_date": "event_date",
            "achievement": "achievement_award",
            "status": "staff_activity__approval_status__status_code",
        }.items():
            values = list(
                rows.order_by()
                .values(field)
                .annotate(count=Count("pk"))
                .order_by(field)[:101]
            )
            groups[name] = values[:100]
            if len(values) > 100:
                truncated.append(name)
        return Response(
            {
                "count": rows.count(),
                "groups": groups,
                "truncated_groups": truncated,
                "scope": "READ and EXPORT intersection",
            }
        )

    @extend_schema(responses=OpenApiTypes.BINARY, parameters=ACTIVITY_FILTERS)
    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = self.report_rows()
        if rows.count() > 10000:
            raise ValidationError("Narrow the report to at most 10,000 records.")
        stream = io.StringIO()
        writer_ = csv.writer(stream)
        columns = [f.attname for f in CocurricularActivity._meta.concrete_fields]
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
        response["Content-Disposition"] = 'attachment; filename="cocurricular.csv"'
        return response


class LookupViewSet(PrivateResponse, viewsets.ViewSet):
    throttle_classes = (CocurricularThrottle,)
    serializer_class = serializers.Serializer

    @extend_schema(
        operation_id="activity_lookup_catalogue", responses=OpenApiTypes.OBJECT
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
        readable = CocurricularActivity.objects.filter(
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
        elif pk in {
            "categories",
            "organizers",
            "organizations",
            "countries",
            "states",
            "statuses",
            "years",
        }:
            from apps.common_reference.models import Country, State

            model, field = {
                "categories": (refs.CoCurricularCategory, "category_name"),
                "organizers": (refs.Organizer, "organization__organization_name"),
                "organizations": (refs.ExternalOrganization, "organization_name"),
                "countries": (Country, "country_name"),
                "states": (State, "state_name"),
                "statuses": (refs.ApprovalStatus, "status_name"),
                "years": (AcademicYear, "year_code"),
            }[pk]
            rows = model.objects.filter(**{field + "__icontains": search}).order_by(
                field, "pk"
            )
            if pk != "years":
                rows = rows.filter(is_active=True)
            if pk == "organizers":
                rows = rows.filter(organization__is_active=True).select_related(
                    "organization"
                )
            if pk == "states":
                country = serializers.IntegerField(min_value=1).run_validation(
                    request.query_params.get("country")
                )
                rows = rows.filter(country_id=country, country__is_active=True)
            label = lambda row: (
                row.organization.organization_name
                if pk == "organizers"
                else getattr(row, field)
            )
        else:
            raise NotFound()
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [{"id": str(row.pk), "label": label(row)} for row in page]
        )


class CocurricularCategoryWrite(StrictInput, serializers.Serializer):
    category_code = serializers.CharField(max_length=50)
    category_name = serializers.CharField(max_length=150)
    is_active = serializers.BooleanField(required=False)


class CategoryAdminViewSet(PrivateResponse, viewsets.ViewSet):
    """Global shared categories; no delete path and no automatic role grants."""

    serializer_class = CocurricularCategoryWrite
    throttle_classes = (CocurricularThrottle,)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def list(self, request):
        require(request.user, "MASTER", "UPDATE")
        rows = refs.CoCurricularCategory.objects.order_by("category_name", "pk")
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [
                {
                    "id": str(r.pk),
                    "category_code": r.category_code,
                    "category_name": r.category_name,
                    "is_active": r.is_active,
                }
                for r in page
            ]
        )

    def save(self, request, pk=None):
        require(request.user, "MASTER", "UPDATE")
        data = validated(CocurricularCategoryWrite, request, partial=pk is not None)

        @s.command
        def execute():
            require(request.user, "MASTER", "UPDATE")
            row = (
                refs.CoCurricularCategory.objects.select_for_update().get(pk=pk)
                if pk
                else refs.CoCurricularCategory()
            )
            for key, value in data.items():
                setattr(row, key, value)
            row.full_clean()
            row.save()
            record(
                actor=request.user,
                module=s.MODULE,
                action="UPDATE" if pk else "CREATE",
                entity=row,
                details={"fields": sorted(data)},
            )
            return row

        row = invoke(execute)
        return Response(
            {
                "id": str(row.pk),
                "category_code": row.category_code,
                "category_name": row.category_name,
                "is_active": row.is_active,
            },
            status=200 if pk else 201,
        )

    @extend_schema(request=CocurricularCategoryWrite, responses=OpenApiTypes.OBJECT)
    def create(self, request):
        return self.save(request)

    @extend_schema(
        request=CocurricularCategoryWrite,
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("id", str, OpenApiParameter.PATH)],
    )
    def partial_update(self, request, pk=None):
        return self.save(request, pk)
