from django.contrib import admin
from .models import ReferenceAuditEvent


@admin.register(ReferenceAuditEvent)
class ReferenceAuditAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor_id', 'action', 'resource', 'record_id', 'source')
    list_filter = ('action', 'resource', 'source')
    search_fields = ('resource', '=record_id', '=actor_id')
    readonly_fields = ('actor', 'action', 'resource', 'record_id', 'timestamp', 'source', 'before', 'after')
    actions = None

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.has_perm('core.view_referenceauditevent')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
