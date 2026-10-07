from django.db import models
from rest_framework import viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from . import models as m
from .catalogue import RESOURCES, FIELDS, PATHS, RESTRICTED, CONFIDENTIAL, SHARED
from .permissions import PeopleModuleEnabled, scoped, related, permitted
from .serializers import READ, WRITE, Identifier
from .services import Command, execute, set_primary, audit
from .filters import filter_rows
from . import identity
from .context import request_id
from uuid import uuid4


class PeopleActionBody(serializers.Serializer):
    reason = serializers.CharField(max_length=250)
    status = serializers.CharField(required=False)


class InviteBody(serializers.Serializer):
    user_id = Identifier()
    reason = serializers.CharField(max_length=250)


class AcceptBody(serializers.Serializer):
    token = serializers.CharField(max_length=100, write_only=True)


class ProvisionBody(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    reason = serializers.CharField(max_length=250)


class ClaimBody(serializers.Serializer):
    token = serializers.CharField(max_length=100, write_only=True)
    password = serializers.CharField(max_length=128, write_only=True)


class AccountBody(serializers.Serializer):
    active = serializers.BooleanField(required=False)
    email = serializers.EmailField(required=False)
    reason = serializers.CharField(max_length=250)


class PeopleViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "put", "head", "options"]
    permission_classes = [permissions.IsAuthenticated, PeopleModuleEnabled]

    def dispatch(self, request, *args, **kwargs):
        self.correlation_id = uuid4()
        token = request_id.set(self.correlation_id)
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            request_id.reset(token)

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        actor = getattr(self.request, "user", None)
        if (
            actor
            and actor.is_authenticated
            and response.status_code in (400, 403, 404, 409)
        ):
            m.PeopleAudit.objects.create(
                actor=actor,
                resource=PATHS[self.queryset.model],
                record_key="request",
                action="denied",
                outcome="denied",
                source="api",
                correlation_id=self.correlation_id,
                after={"status": response.status_code},
            )
        return response

    def get_queryset(self):
        return related(scoped(self.queryset.model, self.request.user))

    def filter_queryset(self, query):
        return filter_rows(query, self.request.query_params, self.request.user)

    def get_serializer_class(self):
        return (
            WRITE[self.queryset.model]
            if self.action in ("create", "update", "partial_update")
            else READ[self.queryset.model]
        )

    def get_object(self):
        value = self.kwargs["pk"]
        try:
            pk = (
                tuple(Identifier().run_validation(x) for x in value.split(":"))
                if self.queryset.model is m.EmployeeCompetency
                else Identifier().run_validation(value)
            )
        except ValidationError:
            raise NotFound() from None
        if isinstance(pk, tuple) and len(pk) != 2:
            raise NotFound()
        obj = self.get_queryset().filter(pk=pk).first()
        if obj is None:
            raise NotFound()
        return obj

    def expected(self):
        value = self.request.headers.get("If-Match")
        if not value:
            raise ValidationError(
                {"version": "Supply the current version in If-Match."}
            )
        return value.strip('"')

    def render_row(self, row, status=200):
        return Response(
            READ[type(row)](row, context={"request": self.request}).data, status=status
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.render_row(
            execute(
                Command(self.queryset.model, request.user, serializer.validated_data)
            ),
            201,
        )

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = self.get_serializer(
            data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        return self.render_row(
            execute(
                Command(
                    type(obj),
                    request.user,
                    serializer.validated_data,
                    obj.pk,
                    expected_version=self.expected(),
                )
            )
        )

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        audit(obj, request.user, "read", {}, source="api")
        return self.render_row(obj)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        m.PeopleAudit.objects.create(
            actor=request.user,
            resource=PATHS[self.queryset.model],
            record_key="list",
            action="read",
            after={"count": len(response.data.get("results", []))},
            source="api",
        )
        return response

    @extend_schema(request=PeopleActionBody)
    @action(detail=True, methods=["post"])
    def status(self, request, **kwargs):
        obj = self.get_object()
        body = PeopleActionBody(data=request.data)
        body.is_valid(raise_exception=True)
        return self.render_row(
            execute(
                Command(
                    type(obj),
                    request.user,
                    {"status": body.validated_data.get("status")},
                    obj.pk,
                    "status",
                    self.expected(),
                    body.validated_data["reason"],
                )
            )
        )

    @extend_schema(request=PeopleActionBody)
    @action(detail=True, methods=["post"], url_path="set-primary")
    def primary(self, request, **kwargs):
        obj = self.get_object()
        body = PeopleActionBody(data=request.data)
        body.is_valid(raise_exception=True)
        return self.render_row(
            set_primary(
                type(obj),
                obj.pk,
                actor=request.user,
                expected_version=self.expected(),
                reason=body.validated_data["reason"],
            )
        )

    @extend_schema(request=ProvisionBody, responses={201: {"type": "object"}})
    @action(detail=True, methods=["post"])
    def provision(self, request, **kwargs):
        obj = self.get_object()
        body = ProvisionBody(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(
            identity.provision(
                actor=request.user, model=type(obj), pk=obj.pk, **body.validated_data
            ),
            status=201,
        )

    @extend_schema(request=AccountBody, responses={200: {"type": "object"}})
    @action(detail=True, methods=["post"], url_path="account")
    def account(self, request, **kwargs):
        obj = self.get_object()
        body = AccountBody(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(
            identity.manage_account(
                actor=request.user, model=type(obj), pk=obj.pk, **body.validated_data
            )
        )

    def toggle(self, request, action):
        obj = self.get_object()
        body = PeopleActionBody(data=request.data)
        body.is_valid(raise_exception=True)
        return self.render_row(
            execute(
                Command(
                    type(obj),
                    request.user,
                    {},
                    obj.pk,
                    action,
                    self.expected(),
                    body.validated_data["reason"],
                )
            )
        )

    @extend_schema(request=PeopleActionBody)
    @action(detail=True, methods=["post"])
    def activate(self, request, **kwargs):
        return self.toggle(request, "activate")

    @extend_schema(request=PeopleActionBody)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, **kwargs):
        return self.toggle(request, "deactivate")

    @extend_schema(request=InviteBody, responses={201: {"type": "object"}})
    @action(detail=True, methods=["post"])
    def invite(self, request, **kwargs):
        obj = self.get_object()
        body = InviteBody(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(
            identity.invite(
                actor=request.user, model=type(obj), pk=obj.pk, **body.validated_data
            ),
            status=201,
        )

    @extend_schema(request=PeopleActionBody, responses={200: {"type": "object"}})
    @action(detail=True, methods=["post"])
    def unlink(self, request, **kwargs):
        obj = self.get_object()
        body = PeopleActionBody(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(
            identity.unlink(
                actor=request.user,
                model=type(obj),
                pk=obj.pk,
                reason=body.validated_data["reason"],
            )
        )

    @extend_schema(responses={(200, "text/csv"): {"type": "string"}})
    @action(detail=False, methods=["get"])
    def export(self, request):
        import csv, io
        from django.http import HttpResponse
        from rest_framework.exceptions import PermissionDenied

        model = self.queryset.model
        if not permitted(request.user, model, "export") or not permitted(
            request.user, model, "view"
        ):
            raise PermissionDenied()
        query = filter_rows(
            related(scoped(model, request.user, "export")),
            request.query_params,
            request.user,
        )
        rows = list(query[:501])
        if len(rows) > 500:
            raise ValidationError("Narrow filters to at most 500 records.")
        values = READ[model](rows, many=True, context={"request": request}).data
        columns = [
            name
            for name in (values[0] if values else ["id"])
            if name not in ("actions", "masked_fields")
        ]
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(columns)
        for row in values:
            cells = []
            for name in columns:
                value = str(row.get(name) or "")
                if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                    value = "'" + value
                cells.append(value)
            writer.writerow(cells)
        m.PeopleAudit.objects.create(
            actor=request.user,
            resource=PATHS[model],
            record_key="export",
            action="export",
            after={"count": len(rows)},
            source="api",
        )
        response = HttpResponse(stream.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="people-export.csv"'
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["X-Request-ID"] = str(self.correlation_id)
        if (
            isinstance(getattr(response, "data", None), dict)
            and "version" in response.data
        ):
            response["ETag"] = '"' + response.data["version"] + '"'
        return response


VIEWSETS = {}
for model in FIELDS:
    attrs = {"queryset": model.objects.none()}
    if model is m.EmployeeCompetency:
        attrs.update(
            lookup_field="employee_id",
            lookup_url_kwarg="pk",
            lookup_value_regex=r"[0-9]+:[0-9]+",
        )
    if model not in (m.Student, m.Employee):
        attrs.update(
            status=None, invite=None, unlink=None, provision=None, account=None
        )
    if model not in (m.StudentAddress, m.EmployeeAddress, m.EmployeeAssignment):
        attrs["primary"] = None
    if not any(f.name == "is_active" for f in model._meta.fields):
        attrs.update(activate=None, deactivate=None)
    cls = type(model.__name__ + "ViewSet", (PeopleViewSet,), attrs)
    version_parameter = OpenApiParameter(
        "If-Match", str, OpenApiParameter.HEADER, required=True
    )
    parameters = [
        OpenApiParameter(name, str, OpenApiParameter.QUERY)
        for name in FIELDS[model]
        if name.endswith("_id")
    ]
    parameters += [
        OpenApiParameter(name, str, OpenApiParameter.QUERY)
        for name in ("search", "ordering", "page_size")
    ]
    parameters += [
        OpenApiParameter(f.name, str, OpenApiParameter.QUERY)
        for f in model._meta.fields
        if f.choices or f.name in ("is_active", "is_primary")
    ]
    annotations = {
        "create": extend_schema(request=WRITE[model], responses={201: READ[model]}),
        "update": extend_schema(
            request=WRITE[model],
            responses={200: READ[model]},
            parameters=[version_parameter],
        ),
        "partial_update": extend_schema(
            request=WRITE[model],
            responses={200: READ[model]},
            parameters=[version_parameter],
        ),
        "list": extend_schema(parameters=parameters),
    }
    for action_name in ("status", "primary", "activate", "deactivate"):
        if getattr(cls, action_name, None):
            annotations[action_name] = extend_schema(
                request=PeopleActionBody,
                responses={200: READ[model]},
                parameters=[version_parameter],
            )
    cls = extend_schema_view(**annotations)(cls)
    VIEWSETS[model] = cls


class Metadata(APIView):
    permission_classes = [permissions.IsAuthenticated, PeopleModuleEnabled]

    @extend_schema(responses={200: {"type": "object"}})
    def get(self, request):
        resources = []
        for path, (model, _) in RESOURCES.items():
            if not permitted(request.user, model):
                continue
            fields = []
            for name, field in WRITE[model]().fields.items():
                if (
                    name in RESTRICTED
                    and not permitted(request.user, model, "restricted")
                    or name in CONFIDENTIAL
                    and not permitted(request.user, model, "confidential")
                ):
                    continue
                fields.append(
                    {
                        "name": name,
                        "label": name.replace("_", " ").title(),
                        "required": field.required,
                        "nullable": field.allow_null,
                        "kind": "id"
                        if isinstance(field, Identifier)
                        else "date"
                        if isinstance(field, serializers.DateField)
                        else "boolean"
                        if isinstance(field, serializers.BooleanField)
                        else "decimal"
                        if isinstance(field, serializers.DecimalField)
                        else "integer"
                        if isinstance(field, serializers.IntegerField)
                        else "text",
                        "choices": list(getattr(field, "choices", {})),
                    }
                )
            resources.append(
                {
                    "path": path,
                    "title": model._meta.verbose_name_plural.title(),
                    "fields": fields,
                    "can_create": permitted(request.user, model, "add")
                    and (model not in SHARED or request.user.is_superuser),
                }
            )
        response = Response({"resources": resources})
        response["Cache-Control"] = "no-store"
        return response


class AcceptInvitation(APIView):
    permission_classes = [permissions.IsAuthenticated, PeopleModuleEnabled]

    @extend_schema(request=AcceptBody, responses={200: {"type": "object"}})
    def post(self, request):
        body = AcceptBody(data=request.data)
        body.is_valid(raise_exception=True)
        response = Response(
            identity.accept(actor=request.user, token=body.validated_data["token"])
        )
        response["Cache-Control"] = "no-store"
        return response


class Choices(APIView):
    permission_classes = [permissions.IsAuthenticated, PeopleModuleEnabled]

    @extend_schema(responses={200: {"type": "object"}})
    def get(self, request, resource, field):
        if resource not in RESOURCES:
            raise NotFound()
        model = RESOURCES[resource][0]
        if (
            not permitted(request.user, model)
            or field not in FIELDS[model]
            or not field.endswith("_id")
        ):
            raise NotFound()
        relation = model._meta.get_field(field[:-3])
        target = relation.related_model
        if target is None:
            raise NotFound()
        from .integrations.upstream import grants
        from django.db.models import Q

        if target in FIELDS:
            query = related(scoped(target, request.user))
        elif target._meta.app_label == "curriculum_catalog":
            # Deliberate queryset adapter; public read DTO remains consumer contract.
            from .integrations.upstream import course_choices as course_scope

            query = course_scope(target, request.user)
        elif target._meta.app_label == "organization":
            query = target.objects.all()
            condition = Q(pk__in=[])
            if not request.user.is_superuser:
                for grant in grants(request.user):
                    name = target._meta.model_name
                    part = (
                        Q(pk=grant.membership.institution_id)
                        if name == "institution"
                        else Q(institution_id=grant.membership.institution_id)
                        if name == "campus"
                        else Q(campus__institution_id=grant.membership.institution_id)
                    )
                    if name == "campus" and grant.campus_id:
                        part &= Q(pk=grant.campus_id)
                    if name == "department":
                        if grant.campus_id:
                            part &= Q(campus_id=grant.campus_id)
                        if grant.department_id:
                            part &= Q(pk=grant.department_id)
                    limits = grant.record_limits
                    resource_name = {
                        "institution": "institutions",
                        "campus": "campuses",
                        "department": "departments",
                    }[name]
                    if resource_name in limits:
                        part &= Q(pk__in=limits[resource_name])
                    condition |= part
                query = query.filter(condition)
        else:
            if not request.user.is_superuser and not grants(request.user).exists():
                raise NotFound()
            query = target.objects.all()
        if any(f.name == "is_active" for f in target._meta.fields):
            query = query.filter(is_active=True)
        labels = [
            f.name
            for f in target._meta.fields
            if f.name.endswith("_name") or f.name in ("display_name", "course_title")
        ]
        label = labels[0] if labels else target._meta.pk.name
        term = request.query_params.get("search", "")
        if len(term) > 100:
            raise ValidationError("Search too long.")
        if term:
            query = query.filter(**{label + "__icontains": term})
        page = request.query_params.get("page", "1")
        if not page.isdigit() or not 1 <= int(page) <= 10000:
            raise ValidationError("Invalid page.")
        start = (int(page) - 1) * 25
        rows = list(query.order_by(label, "pk")[start : start + 26])
        response = Response(
            {
                "results": [
                    {"id": str(row.pk), "label": str(getattr(row, label))}
                    for row in rows[:25]
                ],
                "has_more": len(rows) > 25,
            }
        )
        response["Cache-Control"] = "no-store"
        return response


from rest_framework.throttling import AnonRateThrottle


class InvitationThrottle(AnonRateThrottle):
    rate = "10/min"


class ClaimInvitation(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [InvitationThrottle]

    @extend_schema(request=ClaimBody, responses={200: {"type": "object"}})
    def post(self, request):
        body = ClaimBody(data=request.data)
        body.is_valid(raise_exception=True)
        response = Response(identity.claim(**body.validated_data))
        response["Cache-Control"] = "no-store"
        return response
