from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .catalogue import RESOURCES,BY_MODEL,writable
from .selectors import scoped

class OrganizationMetadata(APIView):
    @extend_schema(responses={200:dict},tags=['Organization'])
    def get(self,request):
        resources=[]
        for r in RESOURCES:
            fields=[]
            for field in writable(r.model):
                if field.name=='is_active':continue
                fields.append({'name':field.attname,'label':str(field.verbose_name).replace('_',' ').capitalize(),
                    'required':not field.blank and not field.has_default(),
                    'default':field.get_default() if field.has_default() else None,
                    'max':field.max_length,'choices':list(field.choices or []),
                    'kind':'parent' if field.is_relation else 'number' if 'Integer' in field.get_internal_type() else 'text',
                    'parent':BY_MODEL[field.related_model].path if field.is_relation and field.related_model in BY_MODEL else 'states' if field.is_relation else None,
                    'reference':field.is_relation and field.related_model not in BY_MODEL})
            can_create=request.user.is_superuser or bool(r.parent and scoped(r.model._meta.get_field(r.parent).related_model,request.user,write=True).exists())
            resources.append({'path':r.path,'title':r.path.replace('-',' ').title(),'id':r.model._meta.pk.name,
                'parent':r.parent,'fields':fields,'can_create':can_create,'can_manage':request.user.is_superuser or scoped(r.model,request.user,write=True).exists(),'count':scoped(r.model,request.user).count()})
        response=Response({'resources':resources,'user_id':request.user.pk})
        response['Cache-Control']='no-store'
        return response
