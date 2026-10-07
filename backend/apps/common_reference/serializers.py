from rest_framework import serializers
from apps.core.fields import ReferenceTextField
from .resources import RESOURCES
from .selectors import is_available

class StrictBoolean(serializers.BooleanField):
    def to_internal_value(self, value):
        if type(value) is not bool:
            raise serializers.ValidationError("Use a JSON boolean.")
        return value

class StrictParentKey(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if type(data) is not int or not 1 <= data <= 2**self.queryset.model._meta.pk.bits - 1:
            raise serializers.ValidationError("Use a positive JSON integer within the parent ID range.")
        return super().to_internal_value(data)

class CanonicalText(serializers.CharField):
    def __init__(self, *args, model_field, **kwargs):
        self.model_field=model_field
        super().__init__(*args, **kwargs)
    def run_validation(self, data=serializers.empty):
        if data is not serializers.empty and data is not None:
            if not isinstance(data,str): raise serializers.ValidationError("Use a string.")
            data=self.model_field.to_python(data)
        return super().run_validation(data)

class ReferenceSerializer(serializers.ModelSerializer):
    effective_active=serializers.SerializerMethodField()
    def get_effective_active(self,obj) -> bool: return is_available(obj)
    def to_internal_value(self,data):
        if not isinstance(data,dict): raise serializers.ValidationError({"non_field_errors":["Use a JSON object."]})
        extra=set(data)-set(self.writable)
        if extra: raise serializers.ValidationError({key:["Field is not writable."] for key in sorted(extra)})
        return super().to_internal_value(data)

SERIALIZERS={}
for model,path,writable,parent,label in RESOURCES:
    attrs={"writable":writable,"__module__":__name__}
    fields=[model._meta.pk.name,*writable,"effective_active"]
    for name in writable:
        if parent and name==parent+"_id":
            field=model._meta.get_field(parent)
            attrs[name]=StrictParentKey(source=parent,queryset=field.related_model.objects.all(),
                allow_null=field.null,required=not field.null)
        else:
            field=model._meta.get_field(name)
            if isinstance(field,ReferenceTextField):
                attrs[name]=CanonicalText(model_field=field,max_length=field.max_length,allow_null=field.null,
                    allow_blank=field.blank,required=not field.blank)
            else: attrs[name]=StrictBoolean(required=False)
    if parent:
        attrs[parent+"_label"]=serializers.CharField(source=parent+"."+label,read_only=True,allow_null=True)
        attrs[parent+"_is_active"]=serializers.BooleanField(source=parent+".is_active",read_only=True,allow_null=True)
        fields += [parent+"_label",parent+"_is_active"]
    attrs["Meta"]=type("Meta",(),{"model":model,"fields":fields,"read_only_fields":[model._meta.pk.name],"validators":[]})
    cls=type(model.__name__+"Serializer",(ReferenceSerializer,),attrs)
    globals()[cls.__name__]=cls
    SERIALIZERS[model]=cls

class ReferenceErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField()


class ReferenceErrorSerializer(serializers.Serializer):
    error = ReferenceErrorDetailSerializer()
