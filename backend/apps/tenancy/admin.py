from django.contrib import admin
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import Membership, ScopeGrant, InstitutionModule

class PlatformOnly(admin.ModelAdmin):
    def has_module_permission(self,request): return request.user.is_superuser
    def has_view_permission(self,request,obj=None): return request.user.is_superuser
    def has_add_permission(self,request): return request.user.is_superuser
    def has_change_permission(self,request,obj=None): return request.user.is_superuser
    def has_delete_permission(self,request,obj=None): return False
    actions=None
    def changeform_view(self,request,*args,**kwargs):
        with transaction.atomic():
            if request.method=='POST':
                ContentType.objects.select_for_update().get(app_label='organization',model='university')
            return super().changeform_view(request,*args,**kwargs)

admin.site.register(Membership,PlatformOnly)
admin.site.register(ScopeGrant,PlatformOnly)
admin.site.register(InstitutionModule,PlatformOnly)
