import csv

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DomainError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class ContributionThrottle(UserRateThrottle):
    scope = "professional_contributions"


from apps.conferences.api import IdentifierRead, StrictInput, writer
from apps.core.pagination import BoundedPagination
from apps.organization.bulk import safe_cell
from apps.people_master.models import AccountLink, EmployeeAssignment
from apps.staff_activities.models import ActivityAttachment, StaffActivity
from apps.staff_activities.workflow import TRANSITIONS
from apps.staff_profile import models as refs

from . import services as s
from .models import ContributionStatusHistory, StaffProfessionalContribution
from .observability import ObservedResponse, record
from .permissions import activity_scope, principal, require

ContributionFields = writer(StaffProfessionalContribution, "ContributionFields")


class ContributionCount(serializers.IntegerField):
    def __init__(self, **kwargs):
        super().__init__(
            min_value=0, max_value=65535, required=False, allow_null=True, **kwargs
        )

    def to_internal_value(self, data):
        if isinstance(data, (float, bool)):
            raise ValidationError("Use a whole number from 0 to 65,535.")
        return super().to_internal_value(data)


class ContributionWrite(ContributionFields):
    number_of_reviews = ContributionCount()
    number_of_candidates = ContributionCount()

    def validate(self, values):
        from .policy import validate_contribution

        # Partial updates are validated again against the complete locked model by the service.
        candidate = StaffProfessionalContribution(**values)
        if not self.root.partial:
            invoke(validate_contribution, candidate)
        return values


class ContributionContext(StrictInput, serializers.Serializer):
    employee_assignment_id = serializers.IntegerField(min_value=1)
    academic_year_id = serializers.IntegerField(
        min_value=1, allow_null=True, required=False
    )
    context_date = serializers.DateField(required=False)


class ContributionSave(StrictInput, serializers.Serializer):
    context = ContributionContext(required=False)
    activity = ContributionWrite()
    version = serializers.CharField(required=False, max_length=64)


class ContributionWorkflow(StrictInput, serializers.Serializer):
    action = serializers.ChoiceField(choices=list(TRANSITIONS))
    remarks = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )
    version = serializers.CharField(max_length=64)


class ContributionArchive(StrictInput, serializers.Serializer):
    version = serializers.CharField(max_length=64)


class ContributionUpload(StrictInput, serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=s.CATEGORIES)
    version = serializers.CharField(max_length=64)
    replaces = serializers.IntegerField(required=False, min_value=1)

    # Multipart QueryDict is accepted without weakening unknown-field checks.
    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))


class ContributionHistoryRead(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    from_status = serializers.CharField(
        source="from_status.status_code", allow_null=True
    )
    to_status = serializers.CharField(source="to_status.status_code")
    changed_by_id = serializers.CharField(read_only=True)

    class Meta:
        model = ContributionStatusHistory
        fields = (
            "id",
            "from_status",
            "to_status",
            "changed_by_id",
            "changed_at",
            "remarks",
        )


class ContributionRead(IdentifierRead):
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
    contribution_type_name = serializers.CharField(
        source="professional_contribution_type.contribution_name"
    )
    context_summary = serializers.SerializerMethodField()

    def get_context_summary(self, obj) -> list[dict]:
        from .selectors import context_summary

        return context_summary(obj)

    class Meta:
        model = StaffProfessionalContribution
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
        "type",
        "organization",
        "journal",
        "conference_event",
        "programme",
        "course",
        "student",
        "appointment_reference_number",
        "status",
        "verification_status",
        "date_from",
        "date_to",
        "mine",
        "ordering",
        "page",
        "page_size",
    )
]


class ContributionViewSet(ObservedResponse, viewsets.GenericViewSet):
    throttle_classes = (ContributionThrottle,)
    serializer_class = ContributionRead
    pagination_class = BoundedPagination
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StaffProfessionalContribution.objects.none()
        rows = (
            StaffProfessionalContribution.objects.filter(
                staff_activity__deleted_at__isnull=True
            )
            .filter(activity_scope(self.request.user))
            .select_related(
                "staff_activity__employee",
                "staff_activity__approval_status",
                "staff_activity__verification_status",
                "staff_activity__department",
                "professional_contribution_type",
                "organization",
                "journal",
                "conference_event",
                "programme",
                "course",
                "student",
            )
        )
        from .selectors import student_read_scope

        rows = rows.filter(student_read_scope(self.request.user))
        q = self.request.query_params
        for key, path in {
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "type": "professional_contribution_type_id",
            "journal": "journal_id",
            "conference_event": "conference_event_id",
            "programme": "programme_id",
            "course": "course_id",
            "student": "student_id",
            "organization": "organization_id",
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
            "status": "staff_activity__approval_status__status_code",
            "verification_status": "staff_activity__verification_status__status_code",
        }.items():
            if q.get(key):
                rows = rows.filter(**{path: q[key][:30].upper()})
        for key, path in {
            "date_from": "contribution_date__gte",
            "date_to": "contribution_date__lte",
        }.items():
            if q.get(key):
                rows = rows.filter(
                    **{path: serializers.DateField().run_validation(q[key])}
                )
        if q.get("appointment_reference_number"):
            rows = rows.filter(
                appointment_reference_number__icontains=q[
                    "appointment_reference_number"
                ][:150]
            )
        if q.get("search"):
            term = q["search"][:200]
            rows = rows.filter(
                Q(title_topic__icontains=term)
                | Q(appointment_reference_number__icontains=term)
                | Q(organization__organization_name__icontains=term)
            )
        ordering = q.get("ordering", "-contribution_date")
        if ordering.lstrip("-") not in {
            "staff_activity_id",
            "title_topic",
            "contribution_date",
            "professional_contribution_type__contribution_name",
        }:
            raise ValidationError({"ordering": "Unsupported sort field."})
        return rows.order_by(ordering, "-pk")

    @transaction.atomic
    def detail_data(self, row):
        StaffActivity.objects.select_for_update().get(pk=row.pk)
        # Refresh after writes so native timestamp defaults are concrete values.
        row = self.get_queryset().filter(pk=row.pk).first()
        if row is None:
            raise NotFound()
        data = ContributionRead(row).data
        data["version"] = s.version(row.pk)
        from .selectors import duplicate_candidates

        data["duplicate_candidates"] = [
            str(pk) for pk in duplicate_candidates(self.request.user, row)
        ]
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
        data["history"] = ContributionHistoryRead(
            ContributionStatusHistory.objects.filter(activity=parent.pk)
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
            ContributionRead(
                self.paginate_queryset(self.get_queryset()), many=True
            ).data
        )

    def retrieve(self, request, pk=None):
        return Response(self.detail_data(self.get_object()))

    @extend_schema(
        request=ContributionSave,
        responses=ContributionRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    def create(self, request):
        data = validated(ContributionSave, request)
        row = invoke(
            s.save_activity,
            request.user,
            data["activity"],
            context=data.get("context"),
            key=request.headers.get("Idempotency-Key"),
        )
        return Response(self.detail_data(row), status=201)

    @extend_schema(request=ContributionSave, responses=ContributionRead)
    def update(self, request, pk=None):
        self.get_object()
        data = validated(ContributionSave, request)
        values = {
            field.attname: None
            for field in StaffProfessionalContribution._meta.concrete_fields
            if field.null
        }
        values.update(data["activity"])
        row = invoke(
            s.save_activity,
            request.user,
            values,
            context=data.get("context"),
            activity_id=pk,
            expected_version=data.get("version"),
        )
        return Response(self.detail_data(row))

    @extend_schema(request=ContributionSave, responses=ContributionRead)
    def partial_update(self, request, pk=None):
        self.get_object()
        data = validated(ContributionSave, request, partial=True)
        row = invoke(
            s.save_activity,
            request.user,
            data.get("activity", {}),
            context=data.get("context"),
            activity_id=pk,
            expected_version=data.get("version"),
        )
        return Response(self.detail_data(row))

    @extend_schema(request=ContributionArchive, responses={204: None})
    def destroy(self, request, pk=None):
        self.get_object()
        data = validated(ContributionArchive, request)
        invoke(s.archive, request.user, pk, data["version"])
        return Response(status=204)

    @extend_schema(
        request=ContributionWorkflow,
        responses=ContributionRead,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=True
            )
        ],
    )
    @action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        self.get_object()
        data = validated(ContributionWorkflow, request)
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

    @extend_schema(request=ContributionUpload, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        self.get_object()
        data = validated(ContributionUpload, request)
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

    @extend_schema(responses=ContributionHistoryRead(many=True))
    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        self.get_object()
        rows = (
            ContributionStatusHistory.objects.filter(activity_id=pk)
            .select_related("from_status", "to_status")
            .order_by("changed_at", "pk")
        )
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(
            ContributionHistoryRead(page, many=True).data
        )

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def audit_history(self, request, pk=None):
        self.get_object()
        from apps.identity_access.models import ActivityAudit

        rows = ActivityAudit.objects.filter(
            module_code=s.MODULE, entity_name="staff_activity", entity_id=str(pk)
        ).order_by("-pk")
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(
            [
                {
                    "id": str(r.pk),
                    "at": r.activity_at,
                    "action": r.action_code,
                    "actor_id": str(r.user_id) if r.user_id else None,
                    "details": r.details,
                }
                for r in page
            ]
        )

    @extend_schema(request=ContributionSave, responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["post"], url_path="duplicate-preview")
    def duplicate_preview(self, request):
        data = validated(ContributionSave, request)
        return Response(
            {
                "candidates": invoke(
                    s.preview_duplicates,
                    request.user,
                    data["activity"],
                    data.get("context"),
                )
            }
        )

    def report_rows(self):
        return self.get_queryset().filter(activity_scope(self.request.user, "EXPORT"))

    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=ACTIVITY_FILTERS)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        from datetime import timedelta

        from django.utils import timezone

        today = timezone.localdate()
        rows = self.report_rows()
        groups, truncated = {}, []
        for name, field in {
            "type": "professional_contribution_type__contribution_name",
            "journal": "journal_id",
            "conference": "conference_event_id",
            "programme": "programme_id",
            "course": "course_id",
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "organization": "organization__organization_name",
            "contribution_date": "contribution_date",
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
                "recent": {
                    "date_from": today - timedelta(days=29),
                    "date_to": today,
                    "count": rows.filter(
                        contribution_date__range=(today - timedelta(days=29), today)
                    ).count(),
                },
                "recorded_counts": rows.aggregate(
                    reviews=Sum("number_of_reviews"),
                    candidates=Sum("number_of_candidates"),
                    reviews_recorded=Count("number_of_reviews"),
                    candidates_recorded=Count("number_of_candidates"),
                ),
                "time_window": {
                    "date_from": request.query_params.get("date_from"),
                    "date_to": request.query_params.get("date_to"),
                    "date_field": "contribution_date",
                    "unspecified": "all recorded dates and undated contributions",
                },
                "verified": rows.filter(
                    staff_activity__verification_status__status_code="VERIFIED"
                ).count(),
                "pending": rows.filter(
                    staff_activity__verification_status__status_code="PENDING"
                ).count(),
                "groups": groups,
                "truncated_groups": truncated,
                "scope": "READ and EXPORT intersection",
            }
        )

    @extend_schema(responses=OpenApiTypes.BINARY, parameters=ACTIVITY_FILTERS)
    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = self.report_rows()
        count = rows.count()
        if count > 10000:
            raise ValidationError("Narrow the report to at most 10,000 records.")
        upper = rows.order_by("-pk").values_list("pk", flat=True).first() or 0
        columns = [
            f.attname for f in StaffProfessionalContribution._meta.concrete_fields
        ]
        parent_columns = [
            "employee_id",
            "institution_id",
            "campus_id",
            "department_id",
            "academic_year_id",
        ]

        class Echo:
            def write(self, value):
                return value

        def output():
            writer_ = csv.writer(Echo())
            yield writer_.writerow(
                columns + parent_columns + ["assignment_context_date", "status"]
            )
            last, sent = 0, 0
            while sent < 10000:
                # Keyset pages bound driver memory and re-evaluate live read/export scopes.
                batch = list(
                    self.report_rows()
                    .filter(pk__gt=last, pk__lte=upper)
                    .order_by("pk")[: min(100, 10000 - sent)]
                )
                if not batch:
                    break
                for row in batch:
                    parent = row.staff_activity
                    yield writer_.writerow(
                        [
                            safe_cell(value)
                            for value in [
                                *[getattr(row, col) for col in columns],
                                *[getattr(parent, col) for col in parent_columns],
                                parent.start_date,
                                parent.approval_status.status_code,
                            ]
                        ]
                    )
                last = batch[-1].pk
                sent += len(batch)

        record(
            actor=request.user,
            module=s.MODULE,
            action="EXPORT",
            details={"phase": "started", "matching_rows": count, "limit": 10000},
        )
        response = StreamingHttpResponse(
            output(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            'attachment; filename="professional_contributions.csv"'
        )
        return response


class LookupViewSet(ObservedResponse, viewsets.ViewSet):
    throttle_classes = (ContributionThrottle,)
    serializer_class = serializers.Serializer

    @extend_schema(
        operation_id="professional_contributions_lookup_catalogue",
        responses=OpenApiTypes.OBJECT,
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
        readable = StaffProfessionalContribution.objects.filter(
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
            "organizations",
            "journals",
            "conferences",
            "programmes",
            "courses",
            "students",
        }:
            from .selectors import REFERENCES, reference_rows

            name = {
                "organizations": "organization",
                "journals": "journal",
                "conferences": "conference_event",
                "programmes": "programme",
                "courses": "course",
                "students": "student",
            }[pk]
            _, field = REFERENCES[name]
            rows = reference_rows(request.user, name)
            if len(search.strip()) < 2:
                rows = rows.none()
            rows = rows.filter(**{field + "__icontains": search}).order_by(field, "pk")
            label = lambda row: getattr(row, field)
        elif pk in {"types", "statuses", "years"}:
            model, field = {
                "types": (refs.ProfessionalContributionType, "contribution_name"),
                "statuses": (refs.ApprovalStatus, "status_name"),
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
        from .policy import requirements

        return pagination.get_paginated_response(
            [
                {
                    "id": str(row.pk),
                    "label": label(row),
                    **(
                        {"required_fields": invoke(requirements, row.contribution_code)}
                        if pk == "types"
                        else {}
                    ),
                }
                for row in page
            ]
        )


class ProfessionalContributionTypeWrite(StrictInput, serializers.Serializer):
    contribution_code = serializers.CharField(max_length=60)
    contribution_name = serializers.CharField(max_length=180)
    description = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True
    )
    is_active = serializers.BooleanField(required=False)


class TypeAdminViewSet(ObservedResponse, viewsets.ViewSet):
    """Global shared types; no delete path and no automatic role grants."""

    lookup_value_regex = r"[0-9]+"
    serializer_class = ProfessionalContributionTypeWrite
    throttle_classes = (ContributionThrottle,)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def list(self, request):
        require(request.user, "MASTER", "UPDATE")
        rows = refs.ProfessionalContributionType.objects.order_by(
            "contribution_name", "pk"
        )
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [
                {
                    "id": str(r.pk),
                    "contribution_code": r.contribution_code,
                    "contribution_name": r.contribution_name,
                    "description": r.description,
                    "is_active": r.is_active,
                }
                for r in page
            ]
        )

    def save(self, request, pk=None):
        require(request.user, "MASTER", "UPDATE")
        data = validated(
            ProfessionalContributionTypeWrite, request, partial=pk is not None
        )

        @s.command
        def execute():
            require(request.user, "MASTER", "UPDATE")
            row = (
                refs.ProfessionalContributionType.objects.select_for_update().get(pk=pk)
                if pk
                else refs.ProfessionalContributionType()
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
                "contribution_code": row.contribution_code,
                "contribution_name": row.contribution_name,
                "description": row.description,
                "is_active": row.is_active,
            },
            status=200 if pk else 201,
        )

    @extend_schema(
        request=ProfessionalContributionTypeWrite, responses=OpenApiTypes.OBJECT
    )
    def create(self, request):
        return self.save(request)

    @extend_schema(
        request=ProfessionalContributionTypeWrite,
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("id", str, OpenApiParameter.PATH)],
    )
    def partial_update(self, request, pk=None):
        return self.save(request, pk)
