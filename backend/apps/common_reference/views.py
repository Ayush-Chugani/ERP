from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError, PermissionDenied
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from apps.accounts.permissions import ReferencePermissions
from .resources import RESOURCES
from .serializers import SERIALIZERS, ReferenceErrorSerializer
from .selectors import available, related
from .services import write_reference

class ReferenceViewSet(mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,
                       mixins.UpdateModelMixin,viewsets.GenericViewSet):
    permission_classes=[ReferencePermissions]
    http_method_names=["get","post","put","patch","head","options"]
    def get_queryset(self):
        query=related(self.permission_model.objects.all())
        # Global labels, including inactive ones, remain readable on detail for edit forms.
        # Only lists default to selectable rows. Model view permission gates both.
        if self.action != "list": return query
        params=self.request.query_params
        allowed={"search","ordering","is_active","page","page_size"}
        if self.parent: allowed.add(self.parent+"_id")
        if self.permission_model._meta.model_name=="caste": allowed.add("uncategorized")
        if set(params)-allowed: raise ValidationError({"filters":["Unsupported filter."]})
        if any(len(params.getlist(key))!=1 for key in params): raise ValidationError({"filters":["Repeated filters are not supported."]})
        for key in ("page", "page_size"):
            if key in params:
                value = params[key]
                if not value.isascii() or not value.isdigit() or len(value) > 10 or int(value) < 1:
                    raise ValidationError({key: ["Use a positive integer of at most ten digits."]})
        active=params.get("is_active","true")
        if active not in ("true","false","all"): raise ValidationError({"is_active":["Use true, false or all."]})
        if active=="true": query=available(query)
        else:
            if not self.request.user.has_perm("common_reference.maintain_reference"):
                raise PermissionDenied("Inactive catalogue lists require global maintenance permission.")
            if active=="false": query=query.filter(is_active=False)
        if self.parent and self.parent+"_id" in params:
            value=params[self.parent+"_id"]
            maximum = 2**self.permission_model._meta.get_field(self.parent).target_field.bits - 1
            if not value.isascii() or not value.isdigit() or len(value)>10 or not 1 <= int(value) <= maximum:
                raise ValidationError({self.parent+"_id":["Use a positive integer within the parent ID range."]})
            query=query.filter(**{self.parent+"_id":int(value)})
        if "uncategorized" in params:
            value=params["uncategorized"]
            if value not in ("true","false"): raise ValidationError({"uncategorized":["Use true or false."]})
            if self.parent+"_id" in params: raise ValidationError({"uncategorized":["Do not combine with social_category_id."]})
            query=query.filter(social_category__isnull=value=="true")
        search=params.get("search","").strip()
        if len(search)>150: raise ValidationError({"search":["Maximum 150 characters."]})
        if search:
            conditions=Q()
            for name in self.search_fields: conditions |= Q(**{name+"__icontains":search})
            query=query.filter(conditions)
        ordering=params.get("ordering",self.permission_model._meta.pk.name).split(",")
        if any((item[1:] if item.startswith("-") else item) not in self.ordering_fields for item in ordering):
            raise ValidationError({"ordering":["Unsupported ordering field."]})
        return query.order_by(*ordering)
    def perform_create(self,serializer):
        serializer.instance=write_reference(self.permission_model,dict(serializer.validated_data), actor=self.request.user)
    def perform_update(self,serializer):
        serializer.instance=write_reference(self.permission_model,dict(serializer.validated_data),serializer.instance.pk, actor=self.request.user)

VIEWSETS={}
for model,path,writable,parent,label in RESOURCES:
    search=tuple(name for name in writable if name not in ("is_active","requires_verification") and not name.endswith("_id"))
    ordering=(model._meta.pk.name,*writable)
    parameters=[OpenApiParameter("search",str,description="Case/accent-insensitive substring search over: " + ", ".join(search) + ". Maximum 150 characters."),OpenApiParameter("ordering",str,description="Comma-separated allowlist: "+", ".join(ordering)),
                OpenApiParameter("is_active",str,enum=["true","false","all"],description="Default true includes active ancestors. false/all require maintenance authority.")]
    if parent: parameters.append(OpenApiParameter(parent+"_id",int))
    if model._meta.model_name=="caste": parameters.append(OpenApiParameter("uncategorized",bool,description="Mutually exclusive with social_category_id"))
    cls=type(model.__name__+"ViewSet",(ReferenceViewSet,),{"__module__":__name__,"permission_model":model,
        "queryset":model.objects.all(),"serializer_class":SERIALIZERS[model],"parent":parent,"search_fields":search,"ordering_fields":ordering})
    cls=extend_schema_view(list=extend_schema(parameters=parameters, description="Requires the model view permission. Visibility is filtered before counts and pagination. Defaults to active rows with active ancestors. Page size defaults to 25 and is capped at 100; primary key breaks ordering ties."),retrieve=extend_schema(description="Requires the model view permission. Includes inactive historical selections; effective_active indicates dropdown availability."),create=extend_schema(description="Requires model add permission AND common_reference.maintain_reference. New parent assignments require active ancestors.", responses={201:SERIALIZERS[model],400:ReferenceErrorSerializer,401:ReferenceErrorSerializer,403:ReferenceErrorSerializer,409:ReferenceErrorSerializer}),
                          update=extend_schema(description="Requires model change permission AND common_reference.maintain_reference. Boolean is_active updates deactivate/reactivate without cascading. Unchanged historical parents may be retained.", responses={200:SERIALIZERS[model],400:ReferenceErrorSerializer,401:ReferenceErrorSerializer,403:ReferenceErrorSerializer,409:ReferenceErrorSerializer}),partial_update=extend_schema(description="Requires model change permission AND common_reference.maintain_reference. Boolean is_active updates deactivate/reactivate without cascading. Unchanged historical parents may be retained.", responses={200:SERIALIZERS[model],400:ReferenceErrorSerializer,401:ReferenceErrorSerializer,403:ReferenceErrorSerializer,409:ReferenceErrorSerializer}))(cls)
    globals()[cls.__name__]=cls
    VIEWSETS[path]=cls


