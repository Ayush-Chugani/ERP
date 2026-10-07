import csv
import json
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.academic_calendar.models import AcademicYear
from apps.common_reference.models import DocumentType
from apps.conferences.api import IdentifierRead, StrictInput, writer
from apps.core.pagination import BoundedPagination
from apps.identity_access.audit import record
from apps.organization.bulk import safe_cell
from apps.staff_activities.models import StaffActivity
from apps.staff_profile import models as masters

from . import permissions as p
from . import selectors
from . import services as s
from .models import (
    EvidenceDocument,
    EvidenceDocumentAudit,
    EvidenceDocumentVersion,
    EvidenceTag,
)
from .observability import ObservedResponse


class EvidenceThrottle(UserRateThrottle):
    scope = "evidence"


BaseMetadata = writer(EvidenceDocument, "EvidenceBaseMetadata")


class MetadataWrite(BaseMetadata):
    tags = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=30, required=False
    )

    class Meta(BaseMetadata.Meta):
        fields = (*s.METADATA, "tags")
        validators = ()


class CreateMetadata(MetadataWrite):
    staff_activity_id = serializers.IntegerField(min_value=1)

    class Meta(MetadataWrite.Meta):
        fields = (*MetadataWrite.Meta.fields, "staff_activity_id")


class CreateUpload(StrictInput, serializers.Serializer):
    metadata = serializers.JSONField()
    file = serializers.FileField()

    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))

    def validate_metadata(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                raise ValidationError("Use a JSON metadata object.") from None
        parsed = CreateMetadata(data=value)
        parsed.is_valid(raise_exception=True)
        return parsed.validated_data


class MetadataSave(StrictInput, serializers.Serializer):
    metadata = MetadataWrite(partial=True)
    version = serializers.CharField(max_length=64)


class ReplaceUpload(StrictInput, serializers.Serializer):
    file = serializers.FileField()
    change_reason = serializers.CharField(max_length=1000)
    version = serializers.CharField(max_length=64)

    def to_internal_value(self, data):
        return super().to_internal_value(dict(data.items()))


class WorkflowWrite(StrictInput, serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["verify", "reject-verification", "approve", "reject-approval"]
    )
    remarks = serializers.CharField(max_length=1000)
    version = serializers.CharField(max_length=64)


class ReviewWrite(StrictInput, serializers.Serializer):
    remarks = serializers.CharField(max_length=1000)
    version = serializers.CharField(max_length=64)


class ReasonWrite(StrictInput, serializers.Serializer):
    reason = serializers.CharField(max_length=1000)
    version = serializers.CharField(max_length=64)


class DocumentRead(IdentifierRead):
    employee_name = serializers.CharField(source="staff_activity.employee.display_name")
    employee_id = serializers.CharField(source="staff_activity.employee_id")
    verification = serializers.CharField(source="verification_status.status_code")
    approval = serializers.CharField(source="approval_status.status_code")
    classification = serializers.CharField(source="confidentiality_level.level_code")
    document_type_name = serializers.CharField(source="document_type.document_name")
    evidence_type_name = serializers.CharField(
        source="evidence_type.evidence_type_name", allow_null=True
    )
    issuing_organization_name = serializers.CharField(
        source="issuing_organization.organization_name", allow_null=True
    )
    tags = serializers.SerializerMethodField()
    version_count = serializers.IntegerField(read_only=True)

    def get_tags(self, row) -> list[dict]:
        return [
            {
                "id": str(link.evidence_tag_id),
                "label": link.evidence_tag.tag_name,
                "code": link.evidence_tag.tag_code,
            }
            for link in row.tag_links.all()
        ]

    class Meta:
        model = EvidenceDocument
        fields = "__all__"


class VersionRead(IdentifierRead):
    filename = serializers.CharField(source="file_object.original_file_name")
    mime_type = serializers.CharField(source="file_object.mime_type")
    size_bytes = serializers.IntegerField(source="file_object.file_size_bytes")

    class Meta:
        model = EvidenceDocumentVersion
        fields = (
            "evidence_document_version_id",
            "version_number",
            "change_reason",
            "uploaded_by_user",
            "uploaded_at",
            "is_current",
            "filename",
            "mime_type",
            "size_bytes",
        )


class AuditRead(IdentifierRead):
    class Meta:
        model = EvidenceDocumentAudit
        fields = "__all__"


def data(cls, request):
    result = cls(data=request.data)
    result.is_valid(raise_exception=True)
    return result.validated_data


FILTERS = [
    OpenApiParameter(name, str)
    for name in (
        "search",
        "staff_activity",
        "employee",
        "department",
        "document_type",
        "evidence_type",
        "academic_year",
        "issuing_organization",
        "confidentiality_level",
        "verification",
        "approval",
        "tag",
        "created_by",
        "issue_from",
        "issue_to",
        "expiry_from",
        "expiry_to",
        "expiry",
        "days",
        "deleted",
        "ordering",
        "page",
        "page_size",
    )
]


class DocumentViewSet(ObservedResponse, viewsets.GenericViewSet):
    serializer_class = DocumentRead
    throttle_classes = (EvidenceThrottle,)
    pagination_class = BoundedPagination
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return EvidenceDocument.objects.none()
        q = self.request.query_params
        rows = selectors.documents(self.request.user, deleted=q.get("deleted") == "1")
        for name, path in {
            "staff_activity": "staff_activity_id",
            "employee": "staff_activity__employee_id",
            "department": "staff_activity__department_id",
            "document_type": "document_type_id",
            "evidence_type": "evidence_type_id",
            "academic_year": "academic_year_id",
            "issuing_organization": "issuing_organization_id",
            "confidentiality_level": "confidentiality_level_id",
            "tag": "tag_links__evidence_tag_id",
            "created_by": "created_by_user_id",
        }.items():
            if q.get(name):
                value = serializers.IntegerField(
                    min_value=1, max_value=2**64 - 1
                ).run_validation(q[name])
                rows = rows.filter(**{path: value})
        for name, path in {
            "verification": "verification_status__status_code",
            "approval": "approval_status__status_code",
        }.items():
            if q.get(name):
                rows = rows.filter(**{path: q[name][:30].upper()})
        for name, path in {
            "issue_from": "document_issue_date__gte",
            "issue_to": "document_issue_date__lte",
            "expiry_from": "expiry_date__gte",
            "expiry_to": "expiry_date__lte",
        }.items():
            if q.get(name):
                rows = rows.filter(
                    **{path: serializers.DateField().run_validation(q[name])}
                )
        today = timezone.localdate()
        if q.get("expiry") == "expired":
            rows = rows.filter(expiry_date__lt=today)
        elif q.get("expiry") == "expiring":
            days = serializers.IntegerField(min_value=0, max_value=3660).run_validation(
                q.get("days", 30)
            )
            rows = rows.filter(expiry_date__range=(today, today + timedelta(days=days)))
        elif q.get("expiry") == "missing":
            from django.conf import settings

            rows = rows.filter(
                expiry_date__isnull=True,
                document_type__document_code__in=settings.EVIDENCE_REQUIRED_EXPIRY_TYPES,
            )
        if q.get("search"):
            term = q["search"][:200]
            rows = rows.filter(
                Q(document_title__icontains=term)
                | Q(description__icontains=term)
                | Q(certificate_document_number__icontains=term)
                | Q(issuing_authority__icontains=term)
            )
        order = q.get("ordering", "-pk")
        if order.lstrip("-") not in {
            "pk",
            "document_title",
            "document_issue_date",
            "expiry_date",
            "created_at",
        }:
            raise ValidationError({"ordering": "Unsupported sort field."})
        return rows.order_by(order, "-pk").distinct()

    def detail_data(self, row, deleted=False):
        row = (
            selectors.documents(self.request.user, deleted=deleted)
            .filter(pk=row.pk)
            .first()
        )
        if row is None:
            # A successful soft-delete may be returned as an identifier to a user without trash read.
            return {"deleted": True}
        result = DocumentRead(row).data
        result["version"] = s.version(row)
        actions = []
        for name, resource, verb in (
            ("edit", "DOCUMENT", "UPDATE"),
            ("replace-file", "FILE", "UPDATE"),
            ("verify", "DOCUMENT", "VERIFY"),
            ("reject-verification", "DOCUMENT", "VERIFY"),
            ("approve", "DOCUMENT", "APPROVE"),
            ("reject-approval", "DOCUMENT", "APPROVE"),
            ("soft-delete", "DOCUMENT", "DELETE"),
            ("restore", "TRASH", "UPDATE"),
            ("download", "FILE", "READ"),
            ("preview", "FILE", "READ"),
            ("versions", "HISTORY", "READ"),
            ("audit", "AUDIT", "READ"),
        ):
            try:
                p.document(self.request.user, row, resource, verb, deleted=deleted)
                if deleted and name not in {"restore", "audit"}:
                    continue
                if not deleted and name == "restore":
                    continue
                if name == "edit" and row.approval_status.status_code not in s.EDITABLE:
                    continue
                if name in {
                    "verify",
                    "reject-verification",
                    "approve",
                    "reject-approval",
                }:
                    from django.conf import settings

                    s.independent(
                        self.request.user,
                        row,
                        allow_self=verb == "VERIFY"
                        and settings.EVIDENCE_ALLOW_SELF_VERIFY,
                    )
                    if row.approval_status.status_code not in s.EDITABLE:
                        continue
                    if verb == "VERIFY" and row.verification_status.status_code not in {
                        "PENDING",
                        "REJECTED",
                    }:
                        continue
                    if (
                        verb == "APPROVE"
                        and settings.EVIDENCE_REQUIRE_VERIFIED_APPROVAL
                        and row.verification_status.status_code != "VERIFIED"
                    ):
                        continue
                actions.append(name)
            except (PermissionDenied, NotFound):
                pass
        result["actions"] = actions
        return result

    @extend_schema(parameters=FILTERS)
    def list(self, request):
        return self.get_paginated_response(
            DocumentRead(self.paginate_queryset(self.get_queryset()), many=True).data
        )

    @transaction.atomic
    def retrieve(self, request, pk=None):
        return Response(
            self.detail_data(
                self.get_object(), deleted=request.query_params.get("deleted") == "1"
            )
        )

    @extend_schema(request=CreateUpload, responses=DocumentRead)
    def create(self, request):
        values = data(CreateUpload, request)
        row = s.create_evidence_with_file(
            actor=request.user,
            values=values["metadata"],
            upload=values["file"],
            key=request.headers.get("Idempotency-Key"),
        )
        with transaction.atomic():
            return Response(self.detail_data(row), status=201)

    @extend_schema(request=MetadataSave, responses=DocumentRead)
    def partial_update(self, request, pk=None):
        values = data(MetadataSave, request)
        row = s.update_evidence_metadata(
            actor=request.user,
            document_id=pk,
            values=values["metadata"],
            expected_version=values["version"],
        )
        with transaction.atomic():
            return Response(self.detail_data(row))

    @extend_schema(request=ReplaceUpload, responses=DocumentRead)
    @action(detail=True, methods=["post"], url_path="replace-file")
    def replace_file(self, request, pk=None):
        values = data(ReplaceUpload, request)
        row = s.replace_evidence_file(
            actor=request.user,
            document_id=pk,
            upload=values["file"],
            change_reason=values["change_reason"],
            expected_version=values["version"],
            key=request.headers.get("Idempotency-Key"),
        )
        with transaction.atomic():
            return Response(self.detail_data(row))

    @extend_schema(request=WorkflowWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"])
    def workflow(self, request, pk=None):
        values = data(WorkflowWrite, request)
        row = s.workflow(
            actor=request.user,
            document_id=pk,
            action=values["action"],
            remarks=values["remarks"],
            expected_version=values["version"],
            key=request.headers.get("Idempotency-Key"),
        )
        with transaction.atomic():
            return Response(self.detail_data(row))

    def review_action(self, request, pk, action):
        values = data(ReviewWrite, request)
        row = s.workflow(
            actor=request.user,
            document_id=pk,
            action=action,
            remarks=values["remarks"],
            expected_version=values["version"],
            key=request.headers.get("Idempotency-Key"),
        )
        with transaction.atomic():
            return Response(self.detail_data(row))

    @extend_schema(request=ReviewWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        return self.review_action(request, pk, "verify")

    @extend_schema(request=ReviewWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"], url_path="reject-verification")
    def reject_verification(self, request, pk=None):
        return self.review_action(request, pk, "reject-verification")

    @extend_schema(request=ReviewWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        return self.review_action(request, pk, "approve")

    @extend_schema(request=ReviewWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"], url_path="reject-approval")
    def reject_approval(self, request, pk=None):
        return self.review_action(request, pk, "reject-approval")

    def change_deleted(self, request, pk, restore):
        values = data(ReasonWrite, request)
        row = s.deletion(
            actor=request.user,
            document_id=pk,
            restore=restore,
            reason=values["reason"],
            expected_version=values["version"],
            key=request.headers.get("Idempotency-Key"),
        )
        with transaction.atomic():
            return Response(self.detail_data(row, deleted=not restore))

    @extend_schema(request=ReasonWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"], url_path="soft-delete")
    def soft_delete(self, request, pk=None):
        return self.change_deleted(request, pk, False)

    @extend_schema(request=ReasonWrite, responses=DocumentRead)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        return self.change_deleted(request, pk, True)

    @extend_schema(responses=VersionRead(many=True))
    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        row = self.get_object()
        p.document(request.user, row, "HISTORY", "READ")
        rows = (
            EvidenceDocumentVersion.objects.filter(evidence_document=row)
            .select_related("file_object")
            .order_by("-version_number")
        )
        return self.get_paginated_response(
            VersionRead(self.paginate_queryset(rows), many=True).data
        )

    @extend_schema(responses=AuditRead(many=True))
    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        row = self.get_object()
        p.document(
            request.user,
            row,
            "AUDIT",
            "READ",
            deleted=request.query_params.get("deleted") == "1",
        )
        rows = EvidenceDocumentAudit.objects.filter(evidence_document=row)
        q = request.query_params
        for name, path in {
            "action": "action_code",
            "actor": "performed_by_user_id",
            "version": "evidence_document_version__version_number",
            "ip": "ip_address",
        }.items():
            if q.get(name):
                value = (
                    serializers.IntegerField(min_value=1).run_validation(q[name])
                    if name in {"actor", "version"}
                    else q[name][:45]
                )
                rows = rows.filter(**{path: value})
        for name, path in {
            "date_from": "performed_at__date__gte",
            "date_to": "performed_at__date__lte",
        }.items():
            if q.get(name):
                rows = rows.filter(
                    **{path: serializers.DateField().run_validation(q[name])}
                )
        return self.get_paginated_response(
            AuditRead(self.paginate_queryset(rows.order_by("-pk")), many=True).data
        )

    def binary(self, request, pk, number=None, preview=False):
        stream, file = s.access_file(
            actor=request.user, document_id=pk, version_number=number, preview=preview
        )
        response = FileResponse(
            stream,
            as_attachment=not preview,
            filename=file.original_file_name,
            content_type=file.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = (
            "default-src 'none'; sandbox; frame-ancestors 'self'"
        )
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        return self.binary(request, pk)

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        return self.binary(request, pk, preview=True)

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(
        detail=True, methods=["get"], url_path=r"versions/(?P<number>[0-9]+)/download"
    )
    def version_download(self, request, pk=None, number=None):
        return self.binary(request, pk, number)

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(
        detail=True, methods=["get"], url_path=r"versions/(?P<number>[0-9]+)/preview"
    )
    def version_preview(self, request, pk=None, number=None):
        return self.binary(request, pk, number, True)

    def report_rows(self):
        return self.get_queryset().filter(
            p.scope(self.request.user, "DOCUMENT", "EXPORT")
        )

    @extend_schema(parameters=FILTERS, responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.report_rows()
        groups = {}
        for label, field in {
            "document_type": "document_type__document_name",
            "academic_year": "academic_year_id",
            "organization": "issuing_organization__organization_name",
            "classification": "confidentiality_level__level_code",
            "verification": "verification_status__status_code",
            "approval": "approval_status__status_code",
            "tag": "tag_links__evidence_tag__tag_name",
        }.items():
            groups[label] = list(
                rows.order_by()
                .values(field)
                .annotate(count=Count("pk", distinct=True))
                .order_by(field)[:100]
            )
        audits = EvidenceDocumentAudit.objects.filter(
            evidence_document_id__in=rows.values("pk"),
            action_code__in=["PREVIEW", "DOWNLOAD"],
        )
        return Response(
            {
                "count": rows.count(),
                "activity_type_coverage": list(
                    rows.order_by()
                    .values("staff_activity_id", "document_type_id")
                    .annotate(documents=Count("pk", distinct=True))
                    .order_by("staff_activity_id", "document_type_id")[:100]
                ),
                "coverage_note": "Visible documents by activity/document type, limited to 100 groups. No mandatory evidence requirements are inferred.",
                "expired": rows.filter(expiry_date__lt=timezone.localdate()).count(),
                "groups": groups,
                "access_counts": list(
                    audits.values("action_code").annotate(count=Count("pk"))
                ),
                "version_count": EvidenceDocumentVersion.objects.filter(
                    evidence_document_id__in=rows.values("pk")
                ).count(),
                "scope": "READ intersect EXPORT; groups limited to 100; tags count documents per tag",
            }
        )

    @extend_schema(parameters=FILTERS, responses=OpenApiTypes.BINARY)
    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = self.report_rows()
        count = rows.count()
        if count > 10000:
            raise ValidationError("Narrow the report to at most 10,000 documents.")
        upper = rows.order_by("-pk").values_list("pk", flat=True).first() or 0

        class Echo:
            def write(self, value):
                return value

        def output():
            writer_ = csv.writer(Echo())
            yield writer_.writerow(
                [
                    "id",
                    "title",
                    "classification",
                    "activity_id",
                    "document_type",
                    "issue_date",
                    "expiry_date",
                    "verification",
                    "approval",
                    "current_version",
                ]
            )
            last = 0
            sent = 0
            while sent < 10000:
                batch = list(
                    self.report_rows()
                    .filter(pk__gt=last, pk__lte=upper)
                    .order_by("pk")[: min(100, 10000 - sent)]
                )
                if not batch:
                    break
                for row in batch:
                    yield writer_.writerow(
                        [
                            safe_cell(v)
                            for v in [
                                row.pk,
                                row.document_title,
                                row.confidentiality_level.level_code,
                                row.staff_activity_id,
                                row.document_type.document_name,
                                row.document_issue_date,
                                row.expiry_date,
                                row.verification_status.status_code,
                                row.approval_status.status_code,
                                row.current_version_number,
                            ]
                        ]
                    )
                last = batch[-1].pk
                sent += len(batch)

        record(
            actor=request.user,
            module="EVIDENCE",
            action="EXPORT",
            details={"phase": "started", "matching_rows": count},
        )
        response = StreamingHttpResponse(
            output(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="evidence.csv"'
        return response


class LookupViewSet(ObservedResponse, viewsets.ViewSet):
    serializer_class = serializers.Serializer
    throttle_classes = (EvidenceThrottle,)

    @extend_schema(
        operation_id="evidence_lookup_catalogue", responses=OpenApiTypes.OBJECT
    )
    def list(self, request):
        p.principal(request.user)
        parents = StaffActivity.objects.filter(
            p.scope(request.user, prefix=""), deleted_at__isnull=True
        )
        if not parents.exists():
            raise PermissionDenied()

        def capable(resource, action):
            return parents.filter(
                p.scope(request.user, resource, action, prefix="")
            ).exists()

        return Response(
            {
                "can_create": capable("DOCUMENT", "CREATE")
                and capable("FILE", "CREATE"),
                "can_export": capable("DOCUMENT", "EXPORT"),
                "can_trash": capable("TRASH", "READ"),
                "can_manage_tags": capable("TAG", "UPDATE"),
            }
        )

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("id", str, OpenApiParameter.PATH)],
    )
    def retrieve(self, request, pk=None):
        self.list(request)
        search = request.query_params.get("search", "")[:200]
        if pk == "activities":
            rows = (
                StaffActivity.objects.filter(
                    p.scope(request.user, prefix=""),
                    p.scope(request.user, "DOCUMENT", "CREATE", prefix=""),
                    deleted_at__isnull=True,
                )
                .select_related("employee")
                .filter(
                    Q(activity_title__icontains=search)
                    | Q(employee__display_name__icontains=search)
                )
                .order_by("-pk")
            )
            if len(search.strip()) < 2:
                rows = rows.none()
            label = lambda row: row.employee.display_name + " / " + row.activity_title
        else:
            mapping = {
                "document-types": (DocumentType, "document_name"),
                "evidence-types": (masters.EvidenceType, "evidence_type_name"),
                "classifications": (masters.ConfidentialityLevel, "level_name"),
                "organizations": (masters.ExternalOrganization, "organization_name"),
                "years": (AcademicYear, "year_code"),
                "tags": (EvidenceTag, "tag_name"),
            }
            if pk not in mapping:
                raise NotFound()
            model, field = mapping[pk]
            rows = model.objects.filter(**{field + "__icontains": search}).order_by(
                field, "pk"
            )
            if pk != "years":
                rows = rows.filter(is_active=True)
            if pk == "organizations" and len(search.strip()) < 2:
                rows = rows.none()
            if pk == "classifications":
                from django.conf import settings

                rows = rows.filter(level_code__in=settings.EVIDENCE_CLASSIFICATIONS)
            label = lambda row: getattr(row, field)
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(
            [{"id": str(row.pk), "label": label(row)} for row in page]
        )


class TagWrite(StrictInput, serializers.Serializer):
    tag_code = serializers.CharField(max_length=60)
    tag_name = serializers.CharField(max_length=120)
    is_active = serializers.BooleanField(required=False)


class TagViewSet(ObservedResponse, viewsets.ViewSet):
    serializer_class = TagWrite
    throttle_classes = (EvidenceThrottle,)
    lookup_value_regex = r"[0-9]+"

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def list(self, request):
        p.require(request.user, "TAG", "UPDATE")
        pagination = BoundedPagination()
        page = pagination.paginate_queryset(
            EvidenceTag.objects.order_by("tag_name", "pk"), request
        )
        return pagination.get_paginated_response(
            [
                {
                    "id": str(row.pk),
                    "tag_code": row.tag_code,
                    "tag_name": row.tag_name,
                    "is_active": row.is_active,
                }
                for row in page
            ]
        )

    @transaction.atomic
    def save_tag(self, request, pk=None):
        p.require(request.user, "TAG", "UPDATE")
        parsed = TagWrite(data=request.data, partial=pk is not None)
        parsed.is_valid(raise_exception=True)
        from django.shortcuts import get_object_or_404

        row = (
            get_object_or_404(EvidenceTag.objects.select_for_update(), pk=pk)
            if pk
            else EvidenceTag()
        )
        for name, value in parsed.validated_data.items():
            setattr(row, name, value)
        from django.core.exceptions import ValidationError as ModelError
        from django.db import IntegrityError

        try:
            row.full_clean()
            row.save()
        except ModelError as error:
            raise ValidationError(error.message_dict) from None
        except IntegrityError:
            raise s.Conflict() from None
        record(
            actor=request.user,
            module="EVIDENCE",
            action="UPDATE" if pk else "CREATE",
            entity=row,
            details={"fields": list(parsed.validated_data)},
        )
        return Response(
            {
                "id": str(row.pk),
                "tag_code": row.tag_code,
                "tag_name": row.tag_name,
                "is_active": row.is_active,
            },
            status=200 if pk else 201,
        )

    @extend_schema(request=TagWrite, responses=OpenApiTypes.OBJECT)
    def create(self, request):
        return self.save_tag(request)

    @extend_schema(request=TagWrite, responses=OpenApiTypes.OBJECT)
    def partial_update(self, request, pk=None):
        return self.save_tag(request, pk)
