from uuid import uuid4
from django.conf import settings
from django.db.models import Q
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_field, OpenApiExample
from rest_framework import serializers, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.pagination import BoundedPagination
from .models import AcademicYear, AcademicTerm, Semester, TimeSlot
from .policies import scoped, campuses, can_create, enabled, permitted
from .services import FIELDS, PATHS, TRANSITIONS, save_record, transition


class CalendarPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return enabled(request.user)

    def has_object_permission(self, request, view, obj):
        return scoped(type(obj), request.user).filter(pk=obj.pk).exists()


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=250, required=False, allow_blank=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - {'reason'}:
            raise ValidationError({'non_field_errors':['Only reason is accepted.']})
        return super().to_internal_value(data)


class CalendarListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        rows = list(data.all() if hasattr(data, 'all') else data)
        if rows:
            model = type(rows[0])
            actor = self.context['request'].user
            ids = [row.pk for row in rows]
            self.context['action_ids'] = {name: set(scoped(model, actor, action=name).filter(pk__in=ids).values_list('pk', flat=True))
                                          for name in ['change', *TRANSITIONS.get(model, {})]}
        return super().to_representation(rows)


class CalendarSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    parent_label = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions(self, obj):
        actor = self.context['request'].user
        names = ['change', *TRANSITIONS.get(type(obj), {})]
        authorized = self.context.get('action_ids')
        return [name for name in names if (obj.pk in authorized[name] if authorized is not None else scoped(type(obj), actor, action=name).filter(pk=obj.pk).exists())
                and (name != 'change' or getattr(obj, 'status', None) != 'CLOSED')
                and (name == 'change' or getattr(obj, 'is_active' if isinstance(obj, TimeSlot) else 'status') in TRANSITIONS[type(obj)][name][1])]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_parent_label(self, obj):
        if isinstance(obj, AcademicTerm):
            return obj.academic_year.year_code
        if isinstance(obj, TimeSlot):
            return obj.campus.campus_name
        return None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_timezone(self, obj):
        return getattr(settings, 'CALENDAR_CAMPUS_TIMEZONES', {}).get(str(obj.campus_id)) if isinstance(obj, TimeSlot) else None

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(FIELDS[self.Meta.model]):
            raise ValidationError({'non_field_errors':['Unknown or read-only fields.']})
        return super().to_internal_value(data)


def make_serializer(model):
    names = [model._meta.pk.name, *FIELDS[model], 'actions', 'parent_label', 'timezone']
    readonly = [model._meta.pk.name]
    if model in (AcademicYear, AcademicTerm):
        names.append('status'); readonly.append('status')
    if model is TimeSlot:
        names.append('is_active'); readonly.append('is_active')
    attrs = {}
    for name in FIELDS[model]:
        if name.endswith('_id'):
            attrs[name] = serializers.IntegerField(min_value=1, max_value=65535)
    attrs['Meta'] = type('Meta', (), {'model': model, 'fields': names, 'read_only_fields': readonly,
        'list_serializer_class': CalendarListSerializer, 'validators': [], 'extra_kwargs': {name: {'validators': []} for name in FIELDS[model] if not name.endswith('_id')}})
    return type(model.__name__ + 'Serializer', (CalendarSerializer,), attrs)


SERIALIZERS = {model: make_serializer(model) for model in FIELDS}
FILTER_FIELDS = {AcademicYear: ['status'], AcademicTerm: ['academic_year_id', 'status', 'term_type'],
                 Semester: ['semester_number'], TimeSlot: ['campus_id', 'is_active', 'is_break']}
SEARCH_FIELDS = {AcademicYear: ['year_code'], AcademicTerm: ['term_code', 'term_name'], Semester: ['semester_name'], TimeSlot: ['slot_code']}


class CalendarViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, CalendarPermission]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    pagination_class = BoundedPagination
    filter_backends = [filters.DjangoFilterBackend, SearchFilter, OrderingFilter]

    def initial(self, request, *args, **kwargs):
        self.correlation_id = str(uuid4())
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        rows = scoped(self.queryset.model, self.request.user)
        if self.queryset.model is AcademicTerm:
            rows = rows.select_related('academic_year')
        if self.queryset.model is TimeSlot:
            rows = rows.select_related('campus__institution__university')
        return rows

    def filter_queryset(self, queryset):
        allowed = {'search', 'ordering', 'page', 'page_size', 'format', *self.filterset_fields}
        if set(self.request.query_params) - allowed:
            raise ValidationError('Unsupported query parameter.')
        for name, values in self.request.query_params.lists():
            if len(values) != 1:
                raise ValidationError({name: 'Supply one value.'})
            if name in ('page', 'page_size', 'academic_year_id', 'campus_id', 'semester_number'):
                if not values[0].isdigit() or not 0 < int(values[0]) <= 4294967295:
                    raise ValidationError({name: 'Use a positive integer.'})
            if name in ('is_active', 'is_break') and values[0] not in ('true', 'false'):
                raise ValidationError({name: 'Use true or false.'})
        order = self.request.query_params.get('ordering', '')
        if order and any(name.lstrip('-') not in self.ordering_fields for name in order.split(',')):
            raise ValidationError({'ordering': 'Unsupported ordering field.'})
        if len(self.request.query_params.get('search', '')) > 100:
            raise ValidationError({'search': 'Use at most 100 characters.'})
        return super().filter_queryset(queryset)

    def perform_create(self, serializer):
        serializer.instance = save_record(self.queryset.model, serializer.validated_data, actor=self.request.user, correlation_id=self.correlation_id)

    def perform_update(self, serializer):
        serializer.instance = save_record(self.queryset.model, serializer.validated_data, actor=self.request.user, pk=serializer.instance.pk, correlation_id=self.correlation_id)

    def lifecycle(self, request, action_name):
        obj = self.get_object()
        payload = ReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = transition(type(obj), obj.pk, action_name, actor=request.user, correlation_id=self.correlation_id, **payload.validated_data)
        return Response(self.get_serializer(row).data)

    @extend_schema(request=ReasonSerializer, examples=[OpenApiExample('Reason', value={'reason':'Reviewed by calendar administrator'}, request_only=True)])
    @action(detail=True, methods=['post'])
    def activate(self, request, **kwargs):
        return self.lifecycle(request, 'activate')

    @extend_schema(request=ReasonSerializer)
    @action(detail=True, methods=['post'])
    def close(self, request, **kwargs):
        return self.lifecycle(request, 'close')

    @extend_schema(request=ReasonSerializer)
    @action(detail=True, methods=['post'])
    def reopen(self, request, **kwargs):
        return self.lifecycle(request, 'reopen')

    @extend_schema(request=ReasonSerializer)
    @action(detail=True, methods=['post'], url_path='open-registration')
    def open_registration(self, request, **kwargs):
        return self.lifecycle(request, 'open_registration')

    @extend_schema(request=ReasonSerializer)
    @action(detail=True, methods=['post'])
    def deactivate(self, request, **kwargs):
        return self.lifecycle(request, 'deactivate')

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        response['X-Request-ID'] = getattr(self, 'correlation_id', '')
        return response


VIEWSETS = {}
for model in FIELDS:
    attrs = {'queryset': model.objects.none(), 'serializer_class': SERIALIZERS[model],
             'filterset_fields': FILTER_FIELDS[model], 'search_fields': SEARCH_FIELDS[model],
             'ordering_fields': [model._meta.pk.name, *FIELDS[model]]}
    # Only publish lifecycle routes applicable to this entity.
    for name in ('activate', 'close', 'reopen', 'open_registration', 'deactivate'):
        if name not in TRANSITIONS.get(model, {}):
            attrs[name] = None
    VIEWSETS[model] = type(model.__name__ + 'ViewSet', (CalendarViewSet,), attrs)


class Metadata(APIView):
    permission_classes = [permissions.IsAuthenticated, CalendarPermission]

    @extend_schema(responses={200: {'type':'object', 'additionalProperties':True}})
    def get(self, request):
        output = []
        for model, names in FIELDS.items():
            fields = []
            for name in names:
                f = model._meta.get_field(name[:-3] if name.endswith('_id') else name)
                kind = 'parent' if name.endswith('_id') else 'choice' if f.choices else 'date' if f.get_internal_type() == 'DateField' else 'time' if f.get_internal_type() == 'TimeField' else 'boolean' if f.get_internal_type() == 'BooleanField' else 'number' if name == 'semester_number' else 'text'
                fields.append({'name':name, 'kind':kind, 'required':not f.blank, 'choices':list(f.choices or []), 'max_length':f.max_length})
            output.append({'path':PATHS[model], 'id':model._meta.pk.name, 'fields':fields, 'can_create':can_create(request.user, model)})
        return Response({'resources':output}, headers={'Cache-Control':'no-store'})


class ParentChoices(APIView):
    permission_classes = [permissions.IsAuthenticated, CalendarPermission]

    @extend_schema(responses={200: {'type':'object', 'additionalProperties':True}})
    def get(self, request):
        query = campuses(request.user, write=True)
        if not (permitted(request.user, TimeSlot, 'add') or permitted(request.user, TimeSlot, 'change')):
            query = query.none()
        query = query.filter(is_active=True, institution__is_active=True, institution__university__is_active=True)
        search = request.query_params.get('search', '')[:100]
        query = query.filter(Q(campus_name__icontains=search) | Q(campus_code__icontains=search)).order_by('campus_name', 'pk')
        paginator = BoundedPagination()
        rows = paginator.paginate_queryset(query, request)
        response = paginator.get_paginated_response([{'id':row.pk, 'label':row.campus_name, 'institution_id':row.institution_id} for row in rows])
        response['Cache-Control'] = 'no-store'
        return response
