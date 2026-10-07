from django.contrib import admin
from django.conf import settings
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class PlatformUserAdmin(UserAdmin):
    # Until scoped account administration exists, only platform superusers edit accounts.
    def has_module_permission(self, request):
        return request.user.is_superuser
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_add_permission(self, request):
        return not settings.IDENTITY_ACCESS_SECURITY_ENABLED and request.user.is_superuser
    def has_change_permission(self, request, obj=None):
        return not settings.IDENTITY_ACCESS_SECURITY_ENABLED and request.user.is_superuser
    def has_delete_permission(self, request, obj=None):
        return not settings.IDENTITY_ACCESS_SECURITY_ENABLED and request.user.is_superuser
