import uuid

from django.conf import settings
from django.http import FileResponse
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.admission_enrolment.models import StudentProgrammeEnrolment
from apps.common_reference.models import DocumentType
from apps.core.pagination import BoundedPagination

from .. import models as m
from .. import permissions as p
from .. import selectors as q
from .. import services as s


class Rate(UserRateThrottle):
    scope = "documents_exit"
    rate = "30/min"


@method_decorator(sensitive_post_parameters(), name="dispatch")
class Base(APIView):
    throttle_classes = (Rate,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not settings.DOCUMENTS_EXIT_ENABLED:
            raise PermissionDenied("Documents and exits are disabled.")
        self.correlation = s.correlation.set(uuid.uuid4().hex)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        patch_vary_headers(response, ["Authorization", "Cookie"])
        if hasattr(self, "correlation"):
            s.correlation.reset(self.correlation)
        return response


def mutation(serializer, fn, **fixed):
    class Mutation(Base):
        @extend_schema(
            request=serializer,
            responses={
                200: OpenApiTypes.OBJECT,
                400: OpenApiTypes.OBJECT,
                401: OpenApiTypes.OBJECT,
                403: OpenApiTypes.OBJECT,
                404: OpenApiTypes.OBJECT,
                409: OpenApiTypes.OBJECT,
                503: OpenApiTypes.OBJECT,
            },
        )
        def post(self, request, **ids):
            data = serializer(data=request.data)
            data.is_valid(raise_exception=True)
            return Response(
                q.summary(fn(actor=request.user, **ids, **fixed, **data.validated_data))
            )

    return Mutation.as_view()


class Records(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id="documents_list")
    def get(self, request, resource):
        if resource == "documents":
            qs = q.documents(request.user)
        elif resource == "certificates":
            qs = q.certificates(request.user)
        elif resource == "exits":
            qs = q.exits(request.user)
        elif resource in ["types", "type-admin"]:
            if resource == "type-admin":
                p.type_admin(request.user)
            elif (
                not request.user.is_superuser
                and not p.memberships(request.user).exists()
            ):
                raise PermissionDenied()
            qs = (
                m.CertificateType.objects.all()
                if resource == "type-admin"
                else m.CertificateType.objects.filter(is_active=True)
            )
        elif resource == "document-types":
            if (
                not request.user.is_superuser
                and not p.memberships(request.user).exists()
            ):
                raise PermissionDenied()
            qs = DocumentType.objects.filter(is_active=True)
        elif resource == "students":
            qs = p.students(request.user, "upload_documents").filter(
                student_status="ACTIVE"
            )
        elif resource == "enrolments":
            qs = StudentProgrammeEnrolment.objects.filter(
                student__in=(
                    p.students(request.user, "finalize_exit")
                    | p.students(request.user, "terminate_enrolment")
                )
            ).select_related("student", "programme")
        else:
            raise NotFound()
        if request.query_params.get("status"):
            field = {
                "documents": "verification_status",
                "certificates": "request_status",
            }.get(resource)
            if field:
                qs = qs.filter(**{field: request.query_params["status"]})
        pager = BoundedPagination()
        rows = pager.paginate_queryset(qs.order_by("-pk"), request)
        if resource == "document-types":
            result = [{"id": str(row.pk), "label": row.document_name} for row in rows]
        elif resource == "students":
            result = [{"id": str(row.pk), "label": row.display_name} for row in rows]
        elif resource == "enrolments":
            result = [
                {
                    "id": str(row.pk),
                    "label": row.student.display_name
                    + " / "
                    + row.programme.programme_name,
                    "status": row.enrolment_status,
                }
                for row in rows
            ]
        else:
            result = [q.summary(row) for row in rows]
        return pager.get_paginated_response(result)


class Detail(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id="documents_detail")
    def get(self, request, resource, pk):
        qs = {
            "documents": q.documents,
            "certificates": q.certificates,
            "exits": q.exits,
        }.get(resource)
        if not qs:
            raise NotFound()
        obj = p.get(qs(request.user), pk)
        return Response(q.summary(obj))


class Download(Base):
    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, resource, pk):
        try:
            stream, file = s.access_file(actor=request.user, resource=resource, pk=pk)
        except NotFound:
            import logging

            logging.getLogger(__name__).warning("m13_file_access_denied")
            raise
        response = FileResponse(
            stream,
            as_attachment=True,
            filename=file.original_file_name,
            content_type=file.mime_type,
        )
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


class Audit(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, resource, pk):
        from apps.core.models import ReferenceAuditEvent

        model = {
            "documents": m.StudentDocument,
            "certificates": m.CertificateRequest,
            "exits": m.StudentExit,
        }.get(resource)
        if model is None:
            raise NotFound()
        obj = p.get(p.scoped(model, request.user, "view_document_audit"), pk)
        qs = ReferenceAuditEvent.objects.filter(
            resource="m13_" + obj._meta.model_name, record_id=obj.pk
        ).order_by("pk")
        pager = BoundedPagination()
        rows = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response(
            [
                {
                    "id": str(row.pk),
                    "actor_id": str(row.actor_id),
                    "timestamp": row.timestamp,
                    "event": row.after,
                }
                for row in rows
            ]
        )
