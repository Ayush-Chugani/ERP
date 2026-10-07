from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DomainError
from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.core.pagination import BoundedPagination
from apps.staff_profile import models as refs

from . import models as m
from . import services
from .permissions import activity_scope, require


class StrictInput:
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError("Expected an object.")
        unknown = set(data) - {k for k, v in self.fields.items() if not v.read_only}
        if unknown:
            raise ValidationError({k: "Unknown or protected field." for k in unknown})
        return super().to_internal_value(data)


def writer(model, name):
    fields = [
        f
        for f in model._meta.concrete_fields
        if not f.primary_key and f.name not in ("created_at", "updated_at")
    ]
    attrs = {
        f.attname: serializers.IntegerField(
            required=not f.null, allow_null=f.null, min_value=1
        )
        for f in fields
        if f.is_relation
    }
    if any(f.name == "doi" for f in fields):
        # Uniqueness is checked after scope authorization by the atomic service.
        attrs["doi"] = serializers.CharField(
            max_length=255, required=False, allow_null=True, allow_blank=True
        )
    attrs["Meta"] = type(
        "Meta",
        (),
        {"model": model, "fields": [f.attname for f in fields], "validators": []},
    )
    return type(name, (StrictInput, serializers.ModelSerializer), attrs)


EventWrite = writer(m.ConferenceEvent, "EventWrite")
ActivityWrite = writer(m.ConferenceActivity, "ActivityWrite")


class Context(StrictInput, serializers.Serializer):
    employee_id = serializers.IntegerField(min_value=1)
    employee_assignment_id = serializers.IntegerField(min_value=1)
    activity_type_id = serializers.IntegerField(min_value=1)
    academic_year_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )


class ClaimWrite(StrictInput, serializers.Serializer):
    indexing_agency_id = serializers.IntegerField(min_value=1)
    source_url = serializers.URLField(
        required=False, allow_null=True, allow_blank=True, max_length=1000
    )
    remarks = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=500
    )


class ActivityCommand(StrictInput, serializers.Serializer):
    context = Context(required=False)
    activity = ActivityWrite(partial=True)
    indexing = ClaimWrite(many=True, required=False, max_length=100)
    version = serializers.CharField(required=False, max_length=64)


class IdentifierRead(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        columns = {f.name: f for f in self.Meta.model._meta.concrete_fields}
        for name, field in list(fields.items()):
            model_field = columns.get(name)
            if name.endswith("_id") or (
                model_field and (model_field.is_relation or model_field.primary_key)
            ):
                source = (
                    model_field.attname
                    if model_field and model_field.is_relation
                    else field.source
                )
                fields[name] = serializers.CharField(
                    source=source if source != name else None,
                    read_only=True,
                    allow_null=field.allow_null,
                )
        return fields


class EventRead(IdentifierRead):
    class Meta:
        model = m.ConferenceEvent
        fields = "__all__"


class ActivityRead(IdentifierRead):
    employee_id = serializers.IntegerField(source="staff_activity.employee_id")
    institution_id = serializers.IntegerField(source="staff_activity.institution_id")
    campus_id = serializers.IntegerField(
        source="staff_activity.campus_id", allow_null=True
    )
    department_id = serializers.IntegerField(
        source="staff_activity.department_id", allow_null=True
    )
    employee_name = serializers.CharField(source="staff_activity.employee.display_name")
    conference_title = serializers.CharField(source="conference_event.conference_title")
    indexing = serializers.SerializerMethodField()

    @extend_schema_field(
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indexing_agency_id": {"type": "string"},
                    "indexing_status": {"type": "string"},
                    "source_url": {"type": "string", "nullable": True},
                    "remarks": {"type": "string", "nullable": True},
                },
            },
        }
    )
    def get_indexing(self, row):
        return getattr(row, "_claims", [])

    class Meta:
        model = m.ConferenceActivity
        fields = "__all__"


def claims_for(rows):
    rows = list(rows)
    lookup = {r.pk: r for r in rows}
    for row in rows:
        row._claims = []
    for claim in m.ConferenceActivityIndexing.objects.filter(
        staff_activity_id__in=lookup
    ).values(
        "staff_activity_id",
        "indexing_agency_id",
        "indexing_status",
        "source_url",
        "remarks",
    ):
        lookup[claim.pop("staff_activity_id")]._claims.append(claim)
    return rows


def invoke(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except DomainError as error:
        raise ValidationError(
            error.message_dict if hasattr(error, "message_dict") else error.messages
        ) from None
    except ObjectDoesNotExist:
        raise NotFound() from None


class PrivateResponse:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        def identifiers(value, key=""):
            if isinstance(value, dict):
                return {k: identifiers(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [identifiers(v, key) for v in value]
            if type(value) is int and (
                key.endswith("_id")
                or key
                in {
                    "id",
                    "staff_activity",
                    "conference_event",
                    "conference_contribution_type",
                    "publication_type",
                    "organizer",
                    "sponsoring_organization",
                    "proceedings_publisher",
                    "participation_level",
                    "event_mode",
                    "state",
                    "country",
                    "indexing_agency",
                }
            ):
                return str(value)
            return value

        if hasattr(response, "data"):
            response.data = identifiers(response.data)
        response["Cache-Control"] = "private, no-store"
        return response


class EventViewSet(PrivateResponse, viewsets.GenericViewSet):
    queryset = m.ConferenceEvent.objects.none()
    lookup_value_regex = r"[0-9]+"
    serializer_class = EventRead
    pagination_class = BoundedPagination

    def get_queryset(self):
        require(self.request.user, "EVENT", "READ")
        rows = m.ConferenceEvent.objects.select_related(
            "organizer__organization", "proceedings_publisher", "country", "state"
        ).order_by("-start_date", "-pk")
        params = self.request.query_params
        if params.get("search"):
            rows = rows.filter(
                Q(conference_title__icontains=params["search"])
                | Q(conference_edition__icontains=params["search"])
                | Q(
                    organizer__organization__organization_name__icontains=params[
                        "search"
                    ]
                )
                | Q(
                    proceedings_publisher__organization__organization_name__icontains=params[
                        "search"
                    ]
                )
            )
        for name in (
            "organizer_id",
            "sponsoring_organization_id",
            "proceedings_publisher_id",
            "participation_level_id",
            "event_mode_id",
            "country_id",
            "state_id",
        ):
            if name in params:
                if not params[name].isdigit():
                    raise ValidationError({name: "Expected an ID."})
                rows = rows.filter(**{name: params[name]})
        if params.get("active") in ("true", "false"):
            rows = rows.filter(is_active=params["active"] == "true")
        for key, lookup in [
            ("date_from", "start_date__gte"),
            ("date_to", "end_date__lte"),
        ]:
            if key in params:
                rows = rows.filter(
                    **{lookup: serializers.DateField().run_validation(params[key])}
                )
        ordering = params.get("ordering", "-start_date")
        if ordering not in (
            "start_date",
            "-start_date",
            "conference_title",
            "-conference_title",
        ):
            raise ValidationError({"ordering": "Unsupported ordering."})
        return rows.order_by(ordering, "pk")

    def list(self, request):
        return self.get_paginated_response(
            self.get_serializer(
                self.paginate_queryset(self.get_queryset()), many=True
            ).data
        )

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(request=EventWrite, responses={201: EventRead})
    def create(self, request):
        require(request.user, "EVENT", "CREATE")
        data = EventWrite(data=request.data)
        data.is_valid(raise_exception=True)
        row = invoke(services.save_event, request.user, data.validated_data)
        return Response(EventRead(row).data, status=201)

    @extend_schema(request=EventWrite, responses=EventRead)
    def partial_update(self, request, pk=None):
        require(request.user, "EVENT", "UPDATE")
        data = EventWrite(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        row = invoke(
            services.save_event, request.user, data.validated_data, event_id=pk
        )
        return Response(EventRead(row).data)


class ActivityViewSet(PrivateResponse, viewsets.GenericViewSet):
    queryset = m.ConferenceActivity.objects.none()
    lookup_value_regex = r"[0-9]+"
    serializer_class = ActivityRead
    pagination_class = BoundedPagination

    def get_queryset(self):
        rows = (
            m.ConferenceActivity.objects.filter(
                activity_scope(self.request.user),
                staff_activity__deleted_at__isnull=True,
            )
            .select_related(
                "staff_activity__employee",
                "conference_event",
                "conference_contribution_type",
                "publication_type",
            )
            .order_by("-staff_activity_id")
        )
        p = self.request.query_params
        search = p.get("search")
        if search:
            rows = rows.filter(
                Q(paper_title__icontains=search)
                | Q(presentation_title__icontains=search)
                | Q(doi__icontains=search)
                | Q(isbn__icontains=search)
                | Q(issn__icontains=search)
                | Q(conference_event__conference_title__icontains=search)
                | Q(conference_event__conference_edition__icontains=search)
                | Q(
                    conference_event__organizer__organization__organization_name__icontains=search
                )
                | Q(
                    conference_event__proceedings_publisher__organization__organization_name__icontains=search
                )
                | Q(staff_activity__employee__display_name__icontains=search)
            )
        fields = {
            "employee": "staff_activity__employee_id",
            "institution": "staff_activity__institution_id",
            "campus": "staff_activity__campus_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "event": "conference_event_id",
            "contribution_type": "conference_contribution_type_id",
            "publication_type": "publication_type_id",
            "country": "conference_event__country_id",
            "state": "conference_event__state_id",
            "event_mode": "conference_event__event_mode_id",
            "participation_level": "conference_event__participation_level_id",
            "organizer": "conference_event__organizer_id",
            "publisher": "conference_event__proceedings_publisher_id",
        }
        for param, path in fields.items():
            if param in p:
                if not p[param].isdigit():
                    raise ValidationError({param: "Expected an ID."})
                rows = rows.filter(**{path: p[param]})
        claims = m.ConferenceActivityIndexing.objects.all()
        if "indexing_agency" in p:
            if not p["indexing_agency"].isdigit():
                raise ValidationError({"indexing_agency": "Expected an ID."})
            claims = claims.filter(indexing_agency_id=p["indexing_agency"])
        if "indexing_status" in p:
            if p["indexing_status"] not in m.ConferenceActivityIndexing.Status.values:
                raise ValidationError({"indexing_status": "Invalid status."})
            claims = claims.filter(indexing_status=p["indexing_status"])
        if "indexing_agency" in p or "indexing_status" in p:
            rows = rows.filter(pk__in=claims.values("staff_activity_id"))
        for key, lookup in [
            ("date_from", "conference_event__start_date__gte"),
            ("date_to", "conference_event__end_date__lte"),
        ]:
            if key in p:
                value = serializers.DateField().run_validation(p[key])
                rows = rows.filter(**{lookup: value})
        if p.get("active") in ("true", "false"):
            rows = rows.filter(conference_event__is_active=p["active"] == "true")
        ordering = p.get("ordering", "-staff_activity_id")
        if ordering not in (
            "staff_activity_id",
            "-staff_activity_id",
            "paper_title",
            "-paper_title",
            "conference_event__start_date",
            "-conference_event__start_date",
        ):
            raise ValidationError({"ordering": "Unsupported ordering."})
        return rows.order_by(ordering, "pk")

    def list(self, request):
        rows = claims_for(self.paginate_queryset(self.get_queryset()))
        return self.get_paginated_response(ActivityRead(rows, many=True).data)

    def retrieve(self, request, pk=None):
        row = self.get_object()
        data = dict(ActivityRead(claims_for([row])[0]).data)
        data["version"] = services.version(row.pk)
        data["permissions"] = [
            verb
            for verb in ("UPDATE", "DELETE", "VERIFY")
            if m.ConferenceActivity.objects.filter(pk=row.pk)
            .filter(activity_scope(request.user, verb))
            .exists()
        ]
        return Response(data)

    @extend_schema(request=ActivityCommand, responses={201: dict})
    def create(self, request):
        data = ActivityCommand(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if not values.get("context"):
            raise ValidationError(
                {"context": "Employee assignment and activity type are required."}
            )
        row = invoke(
            services.save_activity,
            request.user,
            values["activity"],
            context=values.get("context"),
            indexing=values.get("indexing"),
        )
        return Response(
            {"staff_activity": row.pk, "version": services.version(row.pk)}, status=201
        )

    @extend_schema(request=ActivityCommand, responses=dict)
    def partial_update(self, request, pk=None):
        self.get_object()
        data = ActivityCommand(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        row = invoke(
            services.save_activity,
            request.user,
            values.get("activity", {}),
            context=values.get("context"),
            activity_id=int(pk),
            expected_version=values.get("version"),
            indexing=values.get("indexing"),
        )
        return Response({"staff_activity": row.pk, "version": services.version(row.pk)})

    def destroy(self, request, pk=None):
        self.get_object()
        if set(request.data) != {"version"}:
            raise ValidationError("A version is required.")
        invoke(
            services.archive_activity, request.user, int(pk), request.data["version"]
        )
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        self.get_object()

        class VerificationInput(StrictInput, serializers.Serializer):
            version = serializers.CharField(max_length=64)
            indexing_agency_id = serializers.IntegerField(min_value=1)
            status = serializers.ChoiceField(
                choices=m.ConferenceActivityIndexing.Status.choices
            )
            source_url = serializers.URLField(max_length=1000)
            remarks = serializers.CharField(max_length=500)

        data = VerificationInput(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        invoke(
            services.verify_indexing,
            request.user,
            int(pk),
            v["indexing_agency_id"],
            v["status"],
            v["source_url"],
            v["remarks"],
            expected_version=v["version"],
        )
        return Response({"version": services.version(int(pk))})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.get_queryset().filter(activity_scope(request.user, "EXPORT"))
        dimensions = {
            "contribution": "conference_contribution_type_id",
            "employee": "staff_activity__employee_id",
            "department": "staff_activity__department_id",
            "academic_year": "staff_activity__academic_year_id",
            "institution": "staff_activity__institution_id",
            "publication_type": "publication_type_id",
        }
        groups = {
            key: list(
                rows.order_by()
                .values(field)
                .annotate(count=Count("pk"))
                .order_by(field)[:101]
            )
            for key, field in dimensions.items()
        }
        claims = m.ConferenceActivityIndexing.objects.filter(
            staff_activity_id__in=rows.values("pk")
        )
        from django.utils import timezone

        return Response(
            {
                "count": rows.count(),
                "papers": rows.exclude(paper_title__isnull=True)
                .exclude(paper_title="")
                .count(),
                "presentations": rows.exclude(presentation_title__isnull=True)
                .exclude(presentation_title="")
                .count(),
                "awards": rows.exclude(award_name__isnull=True)
                .exclude(award_name="")
                .count(),
                "groups": {key: values[:100] for key, values in groups.items()},
                "truncated_groups": [
                    key for key, values in groups.items() if len(values) > 100
                ],
                "indexing_status": list(
                    claims.values("indexing_status")
                    .annotate(count=Count("staff_activity_id"))
                    .order_by("indexing_status")
                ),
                "generated_at": timezone.now(),
                "filters": dict(request.query_params),
                "scope": "Intersection of authorized READ and EXPORT scope",
            }
        )

    @action(detail=False, methods=["get"])
    def export(self, request):
        import csv
        import io

        from django.http import HttpResponse

        from apps.identity_access.audit import record
        from apps.organization.bulk import safe_cell

        rows = self.get_queryset().filter(activity_scope(request.user, "EXPORT"))
        if rows.count() > 10000:
            raise ValidationError("Narrow the filters to at most 10,000 rows.")
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                "activity_id",
                "employee",
                "conference",
                "paper_title",
                "presentation_title",
                "doi",
                "award_name",
            ]
        )
        count = 0
        for row in rows.iterator(chunk_size=500):
            writer.writerow(
                [
                    safe_cell(v)
                    for v in (
                        row.pk,
                        row.staff_activity.employee.display_name,
                        row.conference_event.conference_title,
                        row.paper_title,
                        row.presentation_title,
                        row.doi,
                        row.award_name,
                    )
                ]
            )
            count += 1
        record(
            actor=request.user,
            module="CONFERENCES",
            action="EXPORT",
            details={"rows": count},
        )
        response = HttpResponse(
            stream.getvalue(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="conferences.csv"'
        response["Cache-Control"] = "no-store"
        return response


class LookupViewSet(PrivateResponse, viewsets.ViewSet):
    serializer_class = serializers.Serializer

    @extend_schema(
        operation_id="conference_lookup_catalogue", responses=OpenApiTypes.OBJECT
    )
    def list(self, request):
        require(request.user, "EVENT", "READ")
        # References are shared global masters; no private organization contacts.
        models = {
            "contribution_types": (refs.ConferenceContributionType, "type_name"),
            "event_modes": (refs.EventMode, "mode_name"),
            "publication_types": (refs.PublicationType, "publication_type_name"),
            "participation_levels": (refs.ParticipationLevel, "level_name"),
            "indexing_agencies": (refs.IndexingAgency, "agency_name"),
        }
        data = {
            key: [
                {"id": r.pk, "label": getattr(r, label)}
                for r in model.objects.filter(is_active=True).order_by("pk")[:500]
            ]
            for key, (model, label) in models.items()
        }
        from rest_framework.exceptions import PermissionDenied

        data["permissions"] = []
        for verb in ("CREATE", "UPDATE"):
            try:
                require(request.user, "EVENT", verb)
                data["permissions"].append("EVENT." + verb)
            except PermissionDenied:
                pass
        from apps.people_master.models import EmployeeAssignment

        if EmployeeAssignment.objects.filter(
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
        ).exists():
            data["permissions"].append("ACTIVITY.CREATE")
        return Response(data)

    @extend_schema(
        operation_id="conference_lookup_choices",
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("id", OpenApiTypes.STR, OpenApiParameter.PATH)],
    )
    def retrieve(self, request, pk=None):
        from apps.academic_calendar.models import AcademicYear
        from apps.common_reference.models import Country, State
        from apps.people_master.models import EmployeeAssignment

        pager = BoundedPagination()
        search = request.query_params.get("search", "")[:200]
        if pk == "assignments":
            rows = EmployeeAssignment.objects.filter(
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
            ).select_related("employee", "campus", "department")
            rows = rows.filter(employee__display_name__icontains=search).order_by("pk")
            page = pager.paginate_queryset(rows, request)
            return pager.get_paginated_response(
                [
                    {
                        "id": r.pk,
                        "employee_id": r.employee_id,
                        "label": f"{r.employee.display_name} / {r.campus.campus_name} / {r.start_date}",
                    }
                    for r in page
                ]
            )
        require(request.user, "EVENT", "READ")
        catalogue = {
            "organizers": (refs.Organizer, "organization__organization_name"),
            "organizations": (refs.ExternalOrganization, "organization_name"),
            "publishers": (refs.Publisher, "organization__organization_name"),
            "countries": (Country, "country_name"),
            "states": (State, "state_name"),
            "years": (AcademicYear, "year_code"),
            "activity_types": (refs.ActivityType, "activity_type_name"),
            "events": (m.ConferenceEvent, "conference_title"),
            "contribution_types": (refs.ConferenceContributionType, "type_name"),
            "event_modes": (refs.EventMode, "mode_name"),
            "publication_types": (refs.PublicationType, "publication_type_name"),
            "participation_levels": (refs.ParticipationLevel, "level_name"),
            "indexing_agencies": (refs.IndexingAgency, "agency_name"),
        }
        if pk not in catalogue:
            raise NotFound()
        model, label = catalogue[pk]
        rows = model.objects.filter(**{label + "__icontains": search}).order_by("pk")
        if any(f.name == "is_active" for f in model._meta.fields):
            rows = rows.filter(is_active=True)
        if pk == "activity_types":
            rows = rows.filter(activity_group="CONFERENCE")
        if "__" in label:
            rows = rows.select_related(label.split("__")[0])
        if pk == "states" and request.query_params.get("country"):
            country = serializers.IntegerField(min_value=1).run_validation(
                request.query_params["country"]
            )
            rows = rows.filter(country_id=country)
        page = pager.paginate_queryset(rows, request)

        def display(row):
            for part in label.split("__"):
                row = getattr(row, part)
            return str(row)

        return pager.get_paginated_response(
            [{"id": r.pk, "label": display(r)} for r in page]
        )
