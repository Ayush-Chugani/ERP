from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError
from .catalogue import RESOURCES,BY_MODEL


class IdentifierFilter(filters.NumberFilter):
    def __init__(self,*args,bits=32,**kwargs):
        self.bits=bits
        super().__init__(*args,**kwargs)
    def filter(self,queryset,value):
        if value is not None:
            if value!=value.to_integral_value() or not 1<=value<2**self.bits:
                raise ValidationError('Use a positive identifier within its storage range.')
            value=int(value)
        return super().filter(queryset,value)


FILTERSETS={}
for resource in RESOURCES:
    attributes={}
    for field in resource.model._meta.fields:
        if field.is_relation:
            attributes[field.attname]=IdentifierFilter(field_name=field.attname,bits=field.target_field.bits)
    model=resource.model
    chain=''
    while BY_MODEL[model].parent:
        parent=BY_MODEL[model].parent
        chain+=('__' if chain else '')+parent
        model=model._meta.get_field(parent).related_model
        attributes[model._meta.pk.name]=IdentifierFilter(field_name=chain+'__pk',bits=model._meta.pk.bits)
    enum_fields={f.name:['exact'] for f in resource.model._meta.fields if f.choices}
    attributes['Meta']=type('Meta',(),{'model':resource.model,'fields':enum_fields})
    FILTERSETS[resource.model]=type(resource.model.__name__+'FilterSet',(filters.FilterSet,),attributes)
