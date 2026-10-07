from uuid import uuid4
import csv
import io
from django.db.models import Q
from django.http import HttpResponse
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_field,
    extend_schema_view,
    OpenApiParameter,
)
from apps.core.pagination import BoundedPagination
from .models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
    CurriculumRevision,
    CurriculumAudit,
)
from .policies import scoped, related, permitted, enabled, PATHS
from .services import FIELDS, Command, execute, key, version, readiness, impact
from .composition import clone_scheme, bulk_compose, reorder
from .integrations.upstream import organization_rows, semester_map, grants
from .public import prerequisite_graph, dependency_impact

ACTIONS = {
    CourseCategory: ["change", "activate", "deactivate"],
    CourseCatalog: ["change", "activate", "deactivate"],
    CurriculumScheme: ["change", "activate", "retire", "clone"],
    CurriculumCourse: ["change", "compose"],
    CoursePrerequisite: ["manage"],
}
SEARCH = {
    CourseCategory: ["category_code", "category_name"],
    CourseCatalog: ["course_code", "course_title"],
    CurriculumScheme: ["scheme_code", "scheme_name"],
    CurriculumCourse: ["course__course_code", "course__course_title"],
    CoursePrerequisite: ["course__course_code", "prerequisite_course__course_code"],
}
FILTERS = {
    CourseCategory: ["is_active"],
    CourseCatalog: [
        "owning_department_id",
        "course_category_id",
        "course_type",
        "is_active",
    ],
    CurriculumScheme: ["programme_id", "specialization_id", "status"],
    CurriculumCourse: [
        "curriculum_scheme_id",
        "semester_id",
        "course_id",
        "is_mandatory",
        "elective_group_code",
    ],
    CoursePrerequisite: ["course_id", "prerequisite_course_id"],
}


class Access(permissions.BasePermission):
    def has_permission(self, request, view):
        return enabled(request.user)

    def has_object_permission(self, request, view, obj):
        return scoped(type(obj), request.user).filter(pk=obj.pk).exists()


@extend_schema_field({"type": "string", "pattern": "^[1-9][0-9]*$"})
class Identifier(serializers.Field):
    def to_internal_value(self, data):
        if (
            type(data) is bool
            or not str(data).isdigit()
            or not 1 <= int(data) <= 2**64 - 1
        ):
            raise serializers.ValidationError("Use a positive decimal integer ID.")
        return int(data)

    def to_representation(self, value):
        return str(value)


class RowList(serializers.ListSerializer):
    def to_representation(self, data):
        rows = list(data.all() if hasattr(data, "all") else data)
        if rows:
            model = type(rows[0])
            actor = self.context["request"].user
            ids = [row.pk for row in rows]
            self.context["versions"] = {
                r.record_key: str(r.version)
                for r in CurriculumRevision.objects.filter(
                    resource=PATHS[model], record_key__in=[key(pk) for pk in ids]
                )
            }
            self.context["capabilities"] = {
                name: {
                    key(pk)
                    for pk in scoped(model, actor, name)
                    .filter(pk__in=ids)
                    .values_list("pk", flat=True)
                }
                for name in ACTIONS[model]
            }
        return super().to_representation(rows)


class RowSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    institution_id = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_institution_id(self, obj):
        from .policies import institution_id

        value = institution_id(obj)
        return str(value) if value else None

    @extend_schema_field(serializers.CharField())
    def get_id(self, obj):
        return key(obj.pk)

    @extend_schema_field(serializers.CharField())
    def get_version(self, obj):
        return (
            self.context["versions"].get(key(obj.pk), "0")
            if "versions" in self.context
            else version(obj)
        )

    @extend_schema_field(serializers.CharField())
    def get_label(self, obj):
        if isinstance(obj, CourseCategory):
            return obj.category_name
        if isinstance(obj, CourseCatalog):
            return obj.course_title
        if isinstance(obj, CurriculumScheme):
            return obj.scheme_name
        if isinstance(obj, CurriculumCourse):
            return obj.course.course_code
        return (
            obj.course.course_code + " requires " + obj.prerequisite_course.course_code
        )

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions(self, obj):
        caps = self.context.get("capabilities")
        actor = self.context["request"].user
        actions = [
            name
            for name in ACTIONS[type(obj)]
            if (
                key(obj.pk) in caps[name]
                if caps is not None
                else scoped(type(obj), actor, name).filter(pk=obj.pk).exists()
            )
        ]
        if isinstance(obj, CurriculumScheme):
            actions = [
                name
                for name in actions
                if not (obj.status != "DRAFT" and name in ("change", "activate"))
                and not (obj.status == "RETIRED" and name == "retire")
            ]
        if (
            isinstance(obj, CurriculumCourse)
            and obj.curriculum_scheme.status != "DRAFT"
        ):
            actions = []
        if hasattr(obj, "is_active"):
            actions = [
                name
                for name in actions
                if name != ("activate" if obj.is_active else "deactivate")
            ]
        return actions

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(FIELDS[self.Meta.model]):
            raise ValidationError(
                {"non_field_errors": ["Unknown or read-only fields."]}
            )
        return super().to_internal_value(data)


def serializer_for(model):
    names = ["id", *FIELDS[model], "version", "actions", "label", "institution_id"]
    attrs = {}
    if model is not CoursePrerequisite:
        names.append(model._meta.pk.name)
        attrs[model._meta.pk.name] = Identifier(read_only=True)
    for name in FIELDS[model]:
        if name.endswith("_id"):
            f = model._meta.get_field(name[:-3])
            attrs[name] = Identifier(required=not f.blank, allow_null=f.null)
    for name in ("status", "is_active"):
        if hasattr(model, name):
            names.append(name)
    attrs["Meta"] = type(
        "Meta",
        (),
        {
            "model": model,
            "fields": names,
            "validators": [],
            "list_serializer_class": RowList,
            "read_only_fields": [
                name for name in ("status", "is_active") if name in names
            ],
            "extra_kwargs": {
                name: {"validators": []}
                for name in FIELDS[model]
                if not name.endswith("_id")
            },
        },
    )
    return type(model.__name__ + "Serializer", (RowSerializer,), attrs)


SERIALIZERS = {model: serializer_for(model) for model in FIELDS}


class ActionBody(serializers.Serializer):
    reason = serializers.CharField(max_length=250, required=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - {"reason"}:
            raise ValidationError({"non_field_errors": ["Only reason is accepted."]})
        return super().to_internal_value(data)


class CloneBody(ActionBody):
    values = serializers.DictField()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - {"reason", "values"}:
            raise ValidationError(
                {"non_field_errors": ["Only reason and values are accepted."]}
            )
        return serializers.Serializer.to_internal_value(self, data)


class CompositionChange(serializers.Serializer):
    id = Identifier(required=False)
    version = serializers.CharField(required=False)
    values = serializers.DictField(required=False, default=dict)
    remove = serializers.BooleanField(required=False, default=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - {
            "id",
            "version",
            "values",
            "remove",
        }:
            raise ValidationError(
                {"non_field_errors": ["Invalid composition command."]}
            )
        if "remove" in data and type(data["remove"]) is not bool:
            raise ValidationError({"remove": "Use a boolean."})
        return super().to_internal_value(data)

    def validate(self, data):
        if data.get("remove") and not data.get("id"):
            raise ValidationError("Removal requires an ID.")
        return data


class BulkBody(serializers.Serializer):
    changes = serializers.ListField(
        child=CompositionChange(), max_length=100, min_length=1
    )
    reason = serializers.CharField(max_length=250, required=False, allow_blank=True)


class ReorderBody(serializers.Serializer):
    semester_id = Identifier()
    record_ids = serializers.ListField(child=Identifier(), min_length=1, max_length=100)
    reason = serializers.CharField(max_length=250, required=False, allow_blank=True)


class CurriculumViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, Access]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    pagination_class = BoundedPagination

    def initial(self, request, *args, **kwargs):
        self.correlation = str(uuid4())
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return related(scoped(self.queryset.model, self.request.user))

    def filter_queryset(self, query):
        model = query.model
        params = self.request.query_params
        allowed = {"search", "ordering", "page", "page_size", "format", *FILTERS[model]}
        if set(params) - allowed:
            raise ValidationError("Unsupported query parameter.")
        for name, values in params.lists():
            if len(values) != 1:
                raise ValidationError({name: "Supply one value."})
            if name in ("page", "page_size") and (
                not values[0].isdigit() or not 1 <= int(values[0]) <= 2**32
            ):
                raise ValidationError({name: "Use a positive integer."})
        for name in FILTERS[model]:
            if name not in params:
                continue
            value = params[name]
            if name.endswith("_id"):
                if name == "specialization_id" and value == "null":
                    value = None
                else:
                    value = Identifier().run_validation(value)
            if name.startswith("is_"):
                if value not in ("true", "false"):
                    raise ValidationError({name: "Use true or false."})
                value = value == "true"
            query = query.filter(**{name: value})
        search = params.get("search", "")
        if len(search) > 100:
            raise ValidationError({"search": "Use at most 100 characters."})
        if search:
            expression = Q()
            for field in SEARCH[model]:
                expression |= Q(**{field + "__icontains": search})
            query = query.filter(expression)
        order = params.get("ordering")
        if order:
            fields = order.split(",")
            allowed_order = set(FIELDS[model]) | {model._meta.pk.name}
            if any(field.lstrip("-") not in allowed_order for field in fields):
                raise ValidationError({"ordering": "Unsupported ordering field."})
            query = query.order_by(*fields)
        return query

    def get_object(self):
        model = self.queryset.model
        value = self.kwargs["pk"]
        if model is CoursePrerequisite:
            parts = value.split(":")
            if len(parts) != 2:
                raise NotFound()
            try:
                pk = tuple(Identifier().run_validation(part) for part in parts)
            except ValidationError:
                raise NotFound() from None
        else:
            try:
                pk = Identifier().run_validation(value)
            except ValidationError:
                raise NotFound() from None
        obj = self.get_queryset().filter(pk=pk).first()
        if obj is None:
            raise NotFound()
        self.check_object_permissions(self.request, obj)
        return obj

    def expected(self):
        value = self.request.headers.get("If-Match")
        if value is None:
            raise ValidationError(
                {"version": "Supply the current version in If-Match."}
            )
        return value.strip('"')

    def perform_create(self, serializer):
        serializer.instance = execute(
            Command(
                self.queryset.model,
                self.request.user,
                serializer.validated_data,
                correlation_id=self.correlation,
            )
        )

    def perform_update(self, serializer):
        serializer.instance = execute(
            Command(
                self.queryset.model,
                self.request.user,
                serializer.validated_data,
                serializer.instance.pk,
                expected_version=self.expected(),
                correlation_id=self.correlation,
            )
        )

    def run_action(self, request, name):
        obj = self.get_object()
        body = ActionBody(data=request.data)
        body.is_valid(raise_exception=True)
        result = execute(
            Command(
                type(obj),
                request.user,
                pk=obj.pk,
                action=name,
                expected_version=self.expected(),
                reason=body.validated_data["reason"],
                correlation_id=self.correlation,
            )
        )
        return (
            Response(self.get_serializer(result).data)
            if result
            else Response(status=204)
        )

    @extend_schema(
        request=ActionBody,
        parameters=[
            OpenApiParameter("If-Match", str, OpenApiParameter.HEADER, required=True)
        ],
    )
    @action(detail=True, methods=["post"])
    def activate(self, request, **kwargs):
        return self.run_action(request, "activate")

    @extend_schema(request=ActionBody)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, **kwargs):
        return self.run_action(request, "deactivate")

    @extend_schema(request=ActionBody)
    @action(detail=True, methods=["post"])
    def retire(self, request, **kwargs):
        return self.run_action(request, "retire")

    @extend_schema(request=ActionBody)
    @action(detail=True, methods=["post"])
    def remove(self, request, **kwargs):
        return self.run_action(request, "remove")

    @extend_schema(responses={200: {"type": "object", "additionalProperties": True}})
    @action(detail=True, methods=["get"])
    def impact(self, request, **kwargs):
        return Response(impact(self.get_object(), request.user))

    @extend_schema(responses={200: {"type": "object", "additionalProperties": True}})
    @action(detail=True, methods=["get"])
    def validate(self, request, **kwargs):
        return Response(readiness(self.get_object(), request.user))

    @extend_schema(request=CloneBody)
    @action(detail=True, methods=["post"])
    def clone(self, request, **kwargs):
        obj = self.get_object()
        body = CloneBody(data=request.data)
        body.is_valid(raise_exception=True)
        payload = SERIALIZERS[CurriculumScheme](
            data=body.validated_data["values"], partial=True
        )
        payload.is_valid(raise_exception=True)
        result = clone_scheme(
            obj.pk,
            actor=request.user,
            expected_version=self.expected(),
            values=payload.validated_data,
            reason=body.validated_data["reason"],
        )
        return Response(self.get_serializer(result).data, status=201)

    @extend_schema(
        request=BulkBody,
        responses={200: {"type": "object", "additionalProperties": True}},
    )
    @action(detail=True, methods=["post"], url_path="bulk-composition")
    def bulk_composition(self, request, **kwargs):
        obj = self.get_object()
        body = BulkBody(data=request.data)
        body.is_valid(raise_exception=True)
        changes = []
        for change in body.validated_data["changes"]:
            data = dict(change)
            if "values" in data:
                serializer = SERIALIZERS[CurriculumCourse](
                    data=data["values"], partial=True
                )
                serializer.is_valid(raise_exception=True)
                data["values"] = serializer.validated_data
            if "id" in data:
                data["id"] = Identifier().run_validation(data["id"])
            changes.append(data)
        return Response(
            bulk_compose(
                obj.pk,
                actor=request.user,
                expected_version=self.expected(),
                changes=changes,
                reason=body.validated_data.get("reason", ""),
            )
        )

    @extend_schema(
        request=ReorderBody,
        responses={200: {"type": "object", "additionalProperties": True}},
    )
    @action(detail=True, methods=["post"])
    def reorder(self, request, **kwargs):
        obj = self.get_object()
        body = ReorderBody(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(
            reorder(
                obj.pk,
                actor=request.user,
                expected_version=self.expected(),
                **body.validated_data,
            )
        )

    @extend_schema(responses={200: {"type": "string"}})
    @action(detail=False, methods=["get"])
    def export(self, request, **kwargs):
        model = self.queryset.model
        if not permitted(request.user, model, "export"):
            raise PermissionDenied()
        query = self.filter_queryset(related(scoped(model, request.user, "export")))
        if query.count() > 5000:
            raise ValidationError("Narrow export to at most 5000 records.")
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", *FIELDS[model]])

        def safe(value):
            text = "" if value is None else str(value)
            return (
                "'" + text
                if text.lstrip().startswith(("=", "+", "-", "@"))
                or text.startswith(("\t", "\r", "\n"))
                else text
            )

        for obj in query:
            writer.writerow(
                [key(obj.pk), *[safe(getattr(obj, name)) for name in FIELDS[model]]]
            )
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{PATHS[model]}.csv"'
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["X-Request-ID"] = getattr(self, "correlation", "")
        if (
            isinstance(getattr(response, "data", None), dict)
            and "version" in response.data
        ):
            response["ETag"] = '"' + response.data["version"] + '"'
        return response


VIEWSETS = {}
for model in FIELDS:
    attrs = {"queryset": model.objects.none(), "serializer_class": SERIALIZERS[model]}
    if model is CoursePrerequisite:
        attrs.update(
            lookup_field="course_id",
            lookup_url_kwarg="pk",
            lookup_value_regex=r"[0-9]+:[0-9]+",
        )
    allowed = {"impact", "export"} | (
        {"activate", "deactivate"}
        if model in (CourseCategory, CourseCatalog)
        else {"activate", "retire", "validate", "clone", "bulk_composition", "reorder"}
        if model is CurriculumScheme
        else {"remove"}
    )
    for name in (
        "activate",
        "deactivate",
        "retire",
        "remove",
        "validate",
        "clone",
        "bulk_composition",
        "reorder",
    ):
        if name not in allowed:
            attrs[name] = None
    view = type(model.__name__ + "ViewSet", (CurriculumViewSet,), attrs)
    writes = {"update", "partial_update"} | (allowed - {"impact", "export", "validate"})
    filter_parameters = [
        OpenApiParameter(name, str, OpenApiParameter.QUERY) for name in FILTERS[model]
    ] + [
        OpenApiParameter(
            "search",
            str,
            OpenApiParameter.QUERY,
            description="Case-insensitive search; maximum 100 characters.",
        ),
        OpenApiParameter(
            "ordering",
            str,
            OpenApiParameter.QUERY,
            description="Comma-separated writable field names or primary key; prefix with - for descending.",
        ),
        OpenApiParameter(
            "page_size",
            int,
            OpenApiParameter.QUERY,
            description="Default 25; maximum 100.",
        ),
    ]
    view = extend_schema_view(
        list=extend_schema(parameters=filter_parameters),
        export=extend_schema(parameters=filter_parameters),
    )(view)
    view = extend_schema_view(
        **{
            name: extend_schema(
                parameters=[
                    OpenApiParameter(
                        "If-Match", str, OpenApiParameter.HEADER, required=True
                    )
                ]
            )
            for name in writes
        }
    )(view)
    VIEWSETS[model] = view


class Metadata(APIView):
    permission_classes = [permissions.IsAuthenticated, Access]

    @extend_schema(responses={200: {"type": "object", "additionalProperties": True}})
    def get(self, request):
        output = []
        for model, names in FIELDS.items():
            fields = []
            for name in names:
                f = model._meta.get_field(name[:-3] if name.endswith("_id") else name)
                kind = (
                    "parent"
                    if name.endswith("_id")
                    else "choice"
                    if f.choices
                    else "date"
                    if f.get_internal_type() == "DateField"
                    else "boolean"
                    if f.get_internal_type() == "BooleanField"
                    else "decimal"
                    if f.get_internal_type() == "DecimalField"
                    else "number"
                    if "Integer" in f.get_internal_type()
                    else "text"
                )
                default = f.get_default() if f.has_default() else None
                if default is not None:
                    default = str(default) if kind in ("decimal", "number") else default
                fields.append(
                    {
                        "name": name,
                        "kind": kind,
                        "required": not f.blank,
                        "choices": list(f.choices or []),
                        "max_length": f.max_length,
                        "default": default,
                    }
                )
            action = "manage" if model is CoursePrerequisite else "add"
            can = permitted(request.user, model, action) and (
                request.user.is_superuser
                or model is not CourseCategory
                and grants(request.user)
                .exclude(role__in=["TEACHER", "STUDENT"])
                .exists()
            )
            output.append(
                {
                    "path": PATHS[model],
                    "fields": fields,
                    "can_create": can,
                    "can_export": permitted(request.user, model, "export"),
                }
            )
        return Response({"resources": output}, headers={"Cache-Control": "no-store"})


class Choices(APIView):
    permission_classes = [permissions.IsAuthenticated, Access]

    @extend_schema(responses={200: {"type": "object", "additionalProperties": True}})
    def get(self, request, kind):
        search = request.query_params.get("search", "")[:100]
        if kind in ("departments", "programmes", "specializations"):
            if not any(
                permitted(request.user, model, "add")
                or permitted(request.user, model, "change")
                for model in (CourseCatalog, CurriculumScheme)
            ):
                raise PermissionDenied()
            query = organization_rows(kind, request.user, write=True).filter(
                is_active=True
            )
            name = {
                "departments": "department_name",
                "programmes": "programme_name",
                "specializations": "specialization_name",
            }[kind]
            query = query.filter(**{name + "__icontains": search}).order_by(name, "pk")
            paginator = BoundedPagination()
            rows = paginator.paginate_queryset(query, request)
            response = paginator.get_paginated_response(
                [{"id": str(row.pk), "label": getattr(row, name)} for row in rows]
            )
        elif kind == "semesters":
            institution = Identifier().run_validation(
                request.query_params.get("institution_id")
            )
            rows = semester_map(actor=request.user, institution_id=institution)
            response = Response(
                {
                    "count": len(rows),
                    "next": None,
                    "results": [
                        {"id": str(pk), "label": name}
                        for pk, (number, name) in rows.items()
                        if search.lower() in name.lower()
                    ],
                }
            )
        else:
            raise NotFound()
        response["Cache-Control"] = "no-store"
        return response
