from django.contrib import admin
from .workflows import RESOURCES


class InspectionOnly(admin.ModelAdmin):
    def has_module_permission(self,request): return request.user.is_active and request.user.is_superuser
    def has_view_permission(self,request,obj=None): return self.has_module_permission(request)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False


for model,_ in RESOURCES.values():
    admin.site.register(model,InspectionOnly)
