from django.contrib import admin
from .models import OrganizationAudit

@admin.register(OrganizationAudit)
class OrganizationAuditAdmin(admin.ModelAdmin):
    list_display=('timestamp','actor_id','resource','record_id','action')
    list_filter=('resource','action')
    search_fields=('resource','=record_id','=actor_id')
    readonly_fields=('timestamp','actor','resource','record_id','action','before','after')
    actions=None
    def has_view_permission(self,request,obj=None):return request.user.is_active and request.user.has_perm('organization.view_organizationaudit')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
