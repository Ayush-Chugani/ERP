from rest_framework import serializers
from apps.common_reference.serializers import StrictBoolean, CanonicalText, StrictParentKey
from apps.core.fields import ReferenceTextField
from .catalogue import RESOURCES,writable
from .selectors import scoped,available
from .services import save_record


class OrganizationSerializer(serializers.ModelSerializer):
    effective_active=serializers.SerializerMethodField()
    can_change=serializers.SerializerMethodField()
    def get_effective_active(self,obj) -> bool: return available(obj)
    def get_can_change(self,obj) -> bool:
        allowed=self.context.get('write_ids')
        if allowed is not None: return obj.pk in allowed
        request=self.context.get('request')
        return bool(request and scoped(type(obj),request.user,write=True).filter(pk=obj.pk).exists())
    def to_internal_value(self,data):
        if not isinstance(data,dict): raise serializers.ValidationError('Use a JSON object.')
        allowed={name for name,field in self.fields.items() if not field.read_only}
        if set(data)-allowed: raise serializers.ValidationError({key:'Field is not writable.' for key in set(data)-allowed})
        return super().to_internal_value(data)
    def get_fields(self):
        fields=super().get_fields()
        request=self.context.get('request')
        if request:
            for field in fields.values():
                if isinstance(field,serializers.PrimaryKeyRelatedField):
                    model=field.queryset.model
                    if model._meta.app_label=='organization': field.queryset=scoped(model,request.user)
                    elif not request.user.has_perm('common_reference.view_state'): field.queryset=model.objects.none()
        return fields
    def create(self,data): return save_record(self.Meta.model,data,actor=self.context['request'].user)
    def update(self,obj,data): return save_record(type(obj),data,pk=obj.pk,actor=self.context['request'].user)

SERIALIZERS={}
for resource in RESOURCES:
    model=resource.model
    attrs={'__module__':__name__}
    fields=[model._meta.pk.name,'created_at','updated_at','effective_active','can_change','is_active']
    attrs['is_active']=StrictBoolean(read_only=True)
    for field in writable(model):
        if field.name=='is_active':continue
        name=field.attname
        fields.append(name)
        if field.is_relation:
            attrs[name]=StrictParentKey(source=field.name,queryset=field.related_model.objects.all(),required=not field.null,allow_null=field.null)
            attrs[field.name+'_label']=serializers.CharField(source=field.name+('.state_name' if field.name=='state' else '.__str__'),read_only=True,allow_null=True)
            fields.append(field.name+'_label')
        elif isinstance(field,ReferenceTextField):
            attrs[name]=CanonicalText(model_field=field,max_length=field.max_length,required=not field.blank,allow_null=field.null,allow_blank=field.blank)
    attrs['Meta']=type('Meta',(),{'model':model,'fields':fields,'read_only_fields':[model._meta.pk.name,'created_at','updated_at'],'validators':[]})
    base=type(model.__name__+'DetailSerializer',(OrganizationSerializer,),attrs)
    SERIALIZERS[model]={}
    for action in ('list','retrieve','create','update','partial_update'):
        cls=type(model.__name__+action.title().replace('_','')+'Serializer',(base,),{'__module__':__name__})
        globals()[cls.__name__]=cls
        SERIALIZERS[model][action]=cls
