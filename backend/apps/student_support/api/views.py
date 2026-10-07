import uuid

from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from drf_spectacular.utils import (
    OpenApiTypes,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.core.pagination import BoundedPagination

from .. import audit
from .. import models as m
from .. import permissions as p
from .. import selectors as q
from .. import services as s
from . import serializers as z


class Rate(UserRateThrottle):
    scope = "student_support"
    rate = "60/min"


class SubmitRate(UserRateThrottle):
    scope = "student_support_submission"
    rate = "10/hour"


@method_decorator(sensitive_post_parameters(), name="dispatch")
class Base(APIView):
    throttle_classes = (Rate,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not settings.STUDENT_SUPPORT_ENABLED:
            raise PermissionDenied("Student support is disabled.")
        self.audit_context = audit.context.set(uuid.uuid4().hex)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        patch_vary_headers(response, ["Authorization", "Cookie"])
        if hasattr(self, "audit_context"):
            audit.context.reset(self.audit_context)
        return response


def mutation(serializer, fn, **fixed):
    class Mutation(Base):
        throttle_classes = [SubmitRate] if fn is s.submit_grievance else [Rate]

        @extend_schema(
            request=serializer,
            responses={
                200: OpenApiTypes.OBJECT,
                400: OpenApiTypes.OBJECT,
                401: OpenApiTypes.OBJECT,
                403: OpenApiTypes.OBJECT,
                404: OpenApiTypes.OBJECT,
                409: OpenApiTypes.OBJECT,
                429: OpenApiTypes.OBJECT,
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
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id="support_list")
    def get(self, request, resource):
        if resource in ["students", "employees", "departments"]:
            from django.db.models import Q

            from apps.organization.models import Department
            from apps.people_master.models import Employee

            if resource == "students":
                qs = p.students(request.user, "manage_mentor_assignments").filter(
                    student_status="ACTIVE"
                )
            elif resource == "employees":
                qs = Employee.objects.filter(
                    institution_id__in=p.students(
                        request.user, "manage_mentor_assignments"
                    ).values("institution_id"),
                    employment_status="ACTIVE",
                )
            else:
                condition = Q(pk__in=[])
                if request.user.is_superuser:
                    condition = Q(
                        campus__institution__is_active=True,
                        campus__institution__university__is_active=True,
                    )
                elif p.can(request.user, "triage_grievance"):
                    for grant in p.grants(request.user):
                        if grant.record_limits:
                            continue
                        part = Q(campus__institution_id=grant.membership.institution_id)
                        if grant.campus_id:
                            part &= Q(campus_id=grant.campus_id)
                        if grant.department_id:
                            part &= Q(pk=grant.department_id)
                        condition |= part
                if p.can(request.user, "submit_own_grievance"):
                    try:
                        condition |= Q(
                            campus__institution_id=p.identity(
                                request.user, "student", True
                            ).institution_id
                        )
                    except NotFound:
                        pass
                qs = Department.objects.filter(
                    condition, is_active=True, campus__is_active=True
                )
            pager = BoundedPagination()
            page = pager.paginate_queryset(qs.order_by("pk"), request)
            return pager.get_paginated_response(
                [
                    {
                        "id": str(row.pk),
                        "label": row.department_name
                        if resource == "departments"
                        else row.display_name,
                    }
                    for row in page
                ]
            )
        if resource == "assignments":
            qs = p.assignments(request.user)
            status = "assignment_status"
        elif resource == "sessions":
            qs = p.sessions(request.user).defer("observations", "action_plan")
            status = "session_status"
        elif resource in ["grievances", "own-grievances"]:
            qs = p.grievances(request.user, own=resource == "own-grievances").defer(
                "subject", "description", "resolution"
            )
            status = "status"
        elif resource == "categories":
            qs = m.GrievanceCategory.objects.filter(is_active=True)
            status = None
            if not (request.user.is_superuser or p.memberships(request.user).exists()):
                raise PermissionDenied()
        elif resource == "category-admin":
            p.category_admin(request.user)
            qs = m.GrievanceCategory.objects.all()
            status = None
        else:
            raise NotFound()
        if status and request.query_params.get("status"):
            qs = qs.filter(**{status: request.query_params["status"]})
        for field in [
            "student_id",
            "employee_id",
            "mentor_assignment_id",
            "department_id",
            "grievance_category_id",
        ]:
            if field in request.query_params and any(
                f.attname == field for f in qs.model._meta.fields
            ):
                parsed = z.pk().run_validation(request.query_params[field])
                qs = qs.filter(**{field: parsed})
        if (
            resource == "sessions"
            and request.query_params.get("follow_up_due") == "true"
        ):
            from django.utils import timezone

            qs = qs.filter(
                session_status="FOLLOW_UP_REQUIRED",
                follow_up_date__lte=timezone.localdate(),
            )
        if resource in ["grievances", "own-grievances"]:
            from rest_framework.serializers import DateField

            for param, lookup in [
                ("submitted_from", "submitted_at__date__gte"),
                ("submitted_to", "submitted_at__date__lte"),
            ]:
                if request.query_params.get(param):
                    qs = qs.filter(
                        **{
                            lookup: DateField().run_validation(
                                request.query_params[param]
                            )
                        }
                    )
        pager = BoundedPagination()
        page = pager.paginate_queryset(qs.order_by("-pk"), request)
        return pager.get_paginated_response([q.summary(row) for row in page])


class Detail(Base):
    @extend_schema(
        responses={
            200: PolymorphicProxySerializer(
                component_name="SupportAuthorizedDetail",
                serializers=[
                    z.AssignmentOutput,
                    z.SessionDetailOutput,
                    z.GrievanceDetailOutput,
                ],
                resource_type_field_name=None,
            ),
            401: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        operation_id="support_detail",
    )
    def get(self, request, resource, pk):
        if resource == "sessions":
            result = q.session_detail(actor=request.user, pk=pk)
        elif resource in ["grievances", "own-grievances"]:
            result = q.grievance_detail(
                actor=request.user, pk=pk, own=resource == "own-grievances"
            )
        elif resource == "assignments":
            result = q.summary(p.get(p.assignments(request.user), pk))
        else:
            raise NotFound()
        return Response(result)


class History(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        obj = p.get(p.grievances(request.user), pk)
        audit.emit(request.user, obj, "grievance_history_read")
        pager = BoundedPagination()
        page = pager.paginate_queryset(
            m.GrievanceAction.objects.filter(grievance=obj).order_by("action_at", "pk"),
            request,
        )
        return pager.get_paginated_response(
            [
                {
                    "id": str(row.pk),
                    "action_at": row.action_at,
                    "action_type": row.action_type,
                    "new_status": row.new_status,
                    "action_notes": row.action_notes,
                }
                for row in page
            ]
        )


class Report(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        if not p.can(request.user, "view_grievance_reports"):
            raise PermissionDenied()
        from rest_framework.serializers import DateField

        values = {
            key: DateField().run_validation(request.query_params[key])
            for key in ["submitted_from", "submitted_to"]
            if key in request.query_params
        }
        return Response(q.report(request.user, **values))
