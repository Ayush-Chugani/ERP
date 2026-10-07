from uuid import uuid4

from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.core.pagination import BoundedPagination
from apps.documents_exit.sharing import download_shared, inspect_shared
from apps.organization.models import Programme
from apps.tenancy.models import Membership

from .. import models as m
from .. import permissions as p
from .. import selectors as q
from .. import services as s


class Rate(UserRateThrottle):
    scope = "communication"
    rate = "60/min"


@method_decorator(sensitive_post_parameters(), name="dispatch")
class Base(APIView):
    throttle_classes = (Rate,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not p.enabled(request.user):
            raise PermissionDenied("Communication is disabled.")
        self.correlation = s.correlation.set(uuid4().hex)

    def handle_exception(self, exc):
        import logging

        status = getattr(exc, "status_code", 500)
        logging.getLogger(__name__).warning("m14_request_failed status=%s", status)
        return super().handle_exception(exc)

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
                403: OpenApiTypes.OBJECT,
                404: OpenApiTypes.OBJECT,
                409: OpenApiTypes.OBJECT,
                503: OpenApiTypes.OBJECT,
            },
        )
        def post(self, request, **ids):
            payload = serializer(data=request.data)
            payload.is_valid(raise_exception=True)
            obj = fn(actor=request.user, **ids, **fixed, **payload.validated_data)
            if isinstance(obj, m.AnnouncementType):
                return Response(
                    {
                        "id": str(obj.pk),
                        "type_code": obj.type_code,
                        "type_name": obj.type_name,
                        "is_active": obj.is_active,
                    }
                )
            return Response(q.summary(obj, True))

    return Mutation.as_view()


def manage_qs(actor):
    condition = Q(pk__in=[])
    for cap in [
        "create_announcement",
        "edit_announcement",
        "review_announcement",
        "approve_announcement",
        "reject_announcement",
        "archive_announcement",
        "manage_attachments",
        "submit_announcement",
    ]:
        condition |= p.scope(actor, cap)
    return q.management_rows(m.Announcement.objects.filter(condition))


class Records(Base):
    @extend_schema(
        operation_id="communication_list",
        responses=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("search", str),
            OpenApiParameter("page", int),
        ],
    )
    def get(self, request, workspace):
        if workspace == "feed":
            rows = q.feed(request.user)
        elif workspace == "manage":
            rows = manage_qs(request.user).order_by("-pk")
            for param, field in [
                ("status", "approval_status"),
                ("type", "announcement_type_id"),
                ("department", "department_id"),
                ("audience", "audience_type"),
            ]:
                if value := request.query_params.get(param):
                    if field.endswith("_id") and not value.isdecimal():
                        raise ValidationError("Invalid filter ID.")
                    rows = rows.filter(**{field: value})
            for param, lookup in [
                ("from", "publish_from__gte"),
                ("until", "publish_from__lt"),
            ]:
                if value := request.query_params.get(param):
                    try:
                        parsed = parse_datetime(value)
                    except ValueError:
                        parsed = None
                    if parsed is None or not timezone.is_aware(parsed):
                        raise ValidationError(
                            "Use an ISO publication filter with timezone."
                        )
                    rows = rows.filter(**{lookup: parsed})
            if value := request.query_params.get("search"):
                rows = rows.filter(
                    Q(title__icontains=value[:250])
                    | Q(description__icontains=value[:250])
                )
        else:
            raise NotFound()
        pager = BoundedPagination()
        page = pager.paginate_queryset(rows, request)
        return pager.get_paginated_response(
            [q.summary(obj, workspace == "manage") for obj in page]
        )


class Detail(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id="communication_detail")
    def get(self, request, workspace, pk):
        obj = parent(request.user, workspace, pk)
        result = q.summary(obj, workspace == "manage")
        links = []
        for link in q.attachment_rows(obj):
            try:
                file = inspect_shared(
                    actor=request.user,
                    file_id=link.file_object_id,
                    institution_id=obj.institution_id,
                )
            except NotFound:
                continue
            links.append(
                {
                    "id": str(file.pk),
                    "name": file.original_file_name,
                    "mime": file.mime_type,
                    "size": file.file_size_bytes,
                    "display_order": link.display_order,
                }
            )
        result["attachments"] = links
        return Response(result)


def parent(actor, workspace, pk):
    if workspace not in ["feed", "manage"]:
        raise NotFound()
    return p.get(q.feed(actor) if workspace == "feed" else manage_qs(actor), pk)


class Download(Base):
    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self, request, workspace, pk, file_id):
        def authorize(actor):
            obj = parent(actor, workspace, pk)
            if not obj.attachments.filter(file_object_id=file_id).exists():
                raise NotFound()
            return obj

        stream, file = download_shared(
            actor=request.user, file_id=file_id, authorize=authorize
        )
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
    def get(self, request, pk):
        p.get(p.management(request.user, "view_audit"), pk)
        pager = BoundedPagination()
        rows = pager.paginate_queryset(q.audit_rows(pk), request)
        return pager.get_paginated_response(
            [
                {
                    "id": str(x.pk),
                    "actor_id": str(x.actor_id),
                    "timestamp": x.timestamp,
                    "before": x.before,
                    "after": x.after,
                }
                for x in rows
            ]
        )


class Lookups(Base):
    @extend_schema(
        responses=OpenApiTypes.OBJECT, parameters=[OpenApiParameter("institution", int)]
    )
    def get(self, request, resource):
        actor = request.user
        if resource in ["types", "type-admin"]:
            if resource == "type-admin":
                p.type_admin(actor)
            elif not p.institutions(actor).exists():
                raise NotFound()
            rows = m.AnnouncementType.objects.all()
            if resource == "types":
                rows = rows.filter(is_active=True)
            render = lambda x: {
                "id": str(x.pk),
                "label": x.type_name,
                "type_code": x.type_code,
                "type_name": x.type_name,
                "is_active": x.is_active,
            }
        elif resource == "institutions":
            rows = p.institutions(actor)
            render = lambda x: {"id": str(x.pk), "label": x.institution_name}
        else:
            value = request.query_params.get("institution", "")
            if not value.isdecimal():
                raise ValidationError("Select an institution.")
            institution_id = int(value)
            # Recipient identities are available only to authorized institution publishers.
            if resource != "departments":
                p.authorize_scope(
                    actor,
                    institution_id,
                    None,
                    "create_announcement"
                    if p.can(actor, "create_announcement")
                    else "edit_announcement",
                )
            if resource == "departments":
                rows = p.department_choices(actor, institution_id)
                render = lambda x: {"id": str(x.pk), "label": x.department_name}
            elif resource == "programmes":
                rows = Programme.objects.filter(
                    department__campus__institution_id=institution_id,
                    is_active=True,
                    department__is_active=True,
                )
                render = lambda x: {"id": str(x.pk), "label": x.programme_name}
            elif resource == "users":
                rows = Membership.objects.filter(
                    institution_id=institution_id, is_active=True, user__is_active=True
                ).select_related("user")
                render = lambda x: {
                    "id": str(x.user_id),
                    "label": x.user.get_username(),
                }
            else:
                raise NotFound()
        pager = BoundedPagination()
        page = pager.paginate_queryset(rows.order_by("pk"), request)
        return pager.get_paginated_response([render(x) for x in page])
