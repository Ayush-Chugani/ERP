from rest_framework import viewsets,mixins,filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError,PermissionDenied
from rest_framework.throttling import UserRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema,extend_schema_view,OpenApiParameter,OpenApiExample
from apps.common_reference.serializers import ReferenceErrorSerializer
from .catalogue import RESOURCES,BY_MODEL
from .serializers import SERIALIZERS
from .filters import FILTERSETS
from .permissions import OrganizationAccess
from .selectors import scoped,related
from .services import save_record,impact
from .bulk import BulkOperations

class OrganizationThrottle(UserRateThrottle):
    rate='120/min'
    scope='organization'

class OrganizationViewSet(BulkOperations,mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,mixins.UpdateModelMixin,viewsets.GenericViewSet):
    permission_classes=[OrganizationAccess]
    throttle_classes=[OrganizationThrottle]
    http_method_names=['get','post','put','patch','head','options']
    filter_backends=[DjangoFilterBackend,filters.SearchFilter,filters.OrderingFilter]
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response['Cache-Control']='no-store'
        return response
    def get_serializer_class(self):return SERIALIZERS[self.model].get(self.action,SERIALIZERS[self.model]['retrieve'])
    def get_queryset(self):
        if getattr(self,'swagger_fake_view',False):return self.model.objects.none()
        write=self.action not in ('list','retrieve','export_csv','offline_snapshot')
        query=scoped(self.model,self.request.user,write=write)
        if self.action in ('list','export_csv','offline_snapshot'):
            params=self.request.query_params
            allowed={'is_active','page','page_size','search','ordering',*self.filterset_class.base_filters}
            if set(params)-allowed or any(len(params.getlist(key))!=1 for key in params):raise ValidationError('Unknown or repeated query parameters.')
            for key in ('page','page_size'):
                value=params.get(key,'1')
                if not value.isascii() or not value.isdigit() or len(value)>10 or int(value)<1:
                    raise ValidationError({key:'Use a positive integer of at most ten digits.'})
            if len(params.get('search',''))>150:raise ValidationError({'search':'Maximum 150 characters.'})
            if any(field.removeprefix('-') not in self.ordering_fields for field in params.get('ordering',self.model._meta.pk.name).split(',')):raise ValidationError({'ordering':'Unsupported field.'})
            active=params.get('is_active','true')
            if active not in ('true','false','all'):raise ValidationError({'is_active':'Use true, false or all.'})
            if active!='true' and not scoped(self.model,self.request.user,write=True).exists():raise PermissionDenied()
            if active!='all':query=query.filter(is_active=active=='true')
            # Default dropdown visibility includes the entire active parent chain.
            if active=='true':
                model=self.model;prefix=''
                while BY_MODEL[model].parent:
                    name=BY_MODEL[model].parent;prefix+=name+'__'
                    query=query.filter(**{prefix+'is_active':True})
                    model=model._meta.get_field(name).related_model
        return related(query)
    def list(self,request,*args,**kwargs):
        rows=self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        ids=[row.pk for row in rows]
        context=self.get_serializer_context()
        context['write_ids']=set(scoped(self.model,request.user,write=True).filter(pk__in=ids).values_list('pk',flat=True))
        return self.get_paginated_response(self.get_serializer(rows,many=True,context=context).data)
    @extend_schema(responses={200:dict},description='Opt-in, scoped active-label snapshot. Maximum 100 rows, five-minute lifetime. Excludes contact details and audit/management metadata; response is not HTTP-cacheable.')
    @action(detail=False,methods=['get'],url_path='offline-snapshot')
    def offline_snapshot(self,request):
        from django.utils import timezone
        from datetime import timedelta
        if request.query_params.get('is_active','true')!='true':raise ValidationError('Offline copies contain active records only.')
        query=self.filter_queryset(self.get_queryset())
        fields=[self.model._meta.pk.name,*[f.name for f in self.model._meta.fields if f.name.endswith(('_code','_name')) and f.name!='legal_name']]
        parent=BY_MODEL[self.model].parent
        if parent:fields.append(parent+'_id')
        rows=list(query.values(*fields)[:101])
        now=timezone.now()
        response=Response({'user_id':request.user.pk,'resource':BY_MODEL[self.model].path,'fetched_at':now.isoformat(),'expires_at':(now+timedelta(minutes=5)).isoformat(),'truncated':len(rows)>100,'records':rows[:100]})
        response['Cache-Control']='no-store'
        return response

    @extend_schema(request=None,responses={200:dict})
    @action(detail=True,methods=['get'],url_path='impact')
    def impact_preview(self,request,**kwargs):return Response(impact(self.get_object(),request.user))
    @extend_schema(request=None,responses={200:dict})
    @action(detail=True,methods=['post'])
    def deactivate(self,request,**kwargs):
        if request.data:raise ValidationError('No request fields are accepted.')
        obj=self.get_object();obj=save_record(self.model,{'is_active':False},pk=obj.pk,actor=request.user)
        return Response(self.get_serializer(obj).data)
    @extend_schema(request=None,responses={200:dict})
    @action(detail=True,methods=['post'])
    def reactivate(self,request,**kwargs):
        if request.data:raise ValidationError('No request fields are accepted.')
        obj=self.get_object();obj=save_record(self.model,{'is_active':True},pk=obj.pk,actor=request.user)
        return Response(self.get_serializer(obj).data)
    @extend_schema(request=dict,responses={200:dict,409:ReferenceErrorSerializer})
    @action(detail=True,methods=['post'])
    def move(self,request,**kwargs):
        obj=self.get_object();parent=BY_MODEL[self.model].parent
        if not parent or set(request.data)!={parent+'_id'}:raise ValidationError('Supply only the new parent ID.')
        serializer=SERIALIZERS[self.model]['partial_update'](obj,data=request.data,partial=True,context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        obj=save_record(self.model,serializer.validated_data,pk=obj.pk,actor=request.user,move=True)
        return Response(self.get_serializer(obj).data)

VIEWSETS={}
for r in RESOURCES:
    fields=[f.name for f in r.model._meta.fields if f.get_internal_type() in ('CharField','EmailField','URLField')]
    cls=type(r.model.__name__+'ViewSet',(OrganizationViewSet,),{'__module__':__name__,'model':r.model,'queryset':r.model.objects.none(),'filterset_class':FILTERSETS[r.model],'search_fields':fields,'ordering_fields':[r.model._meta.pk.name,*fields,'is_active','created_at'],'ordering':[r.model._meta.pk.name]})
    example={}
    for field in r.model._meta.fields:
        if field.primary_key or field.name in ('created_at','updated_at','is_active') or field.blank:continue
        example[field.attname]=1 if field.is_relation else field.choices[0][0] if field.choices else 6 if 'Integer' in field.get_internal_type() else 'EXAMPLE' if field.name.endswith('_code') else 'Example name'
    response=SERIALIZERS[r.model]['retrieve']
    writes={200:response,400:ReferenceErrorSerializer,401:ReferenceErrorSerializer,403:ReferenceErrorSerializer,404:ReferenceErrorSerializer,409:ReferenceErrorSerializer}
    schema_updates=dict(
        list=extend_schema(tags=['Organization'],description='Scope is applied before search, counts, pagination and lookup. Active lists require active ancestors; inactive/all lists require management scope.',parameters=[OpenApiParameter('is_active',str,enum=['true','false','all'])]),
        retrieve=extend_schema(tags=['Organization'],responses={200:response,401:ReferenceErrorSerializer,404:ReferenceErrorSerializer}),
        create=extend_schema(tags=['Organization'],examples=[OpenApiExample(r.model.__name__+' create',value=example,request_only=True)],responses={201:response,400:ReferenceErrorSerializer,401:ReferenceErrorSerializer,403:ReferenceErrorSerializer,409:ReferenceErrorSerializer}),
        update=extend_schema(tags=['Organization'],responses=writes),partial_update=extend_schema(tags=['Organization'],responses=writes),
        deactivate=extend_schema(tags=['Organization'],request=None,responses=writes),reactivate=extend_schema(tags=['Organization'],request=None,responses=writes))
    if r.parent:
        schema_updates['move']=extend_schema(tags=['Organization'],request={'application/json':{'type':'object','additionalProperties':False,'required':[r.parent+'_id'],'properties':{r.parent+'_id':{'type':'integer','minimum':1}}}},responses=writes)
    cls=extend_schema_view(**schema_updates)(cls)
    VIEWSETS[r.path]=cls
