from django.conf import settings
from rest_framework.permissions import BasePermission
from .evaluator import has_object_permission


class IdentityAccessPermission(BasePermission):
    """New endpoints fail closed; existing endpoints keep their staged policies."""
    def has_permission(self, request, view):
        if not settings.IDENTITY_ACCESS_ENABLED or not request.user.is_authenticated:
            return False
        required = getattr(view, 'required_permissions', {}).get(request.method)
        adapter = getattr(view, 'permission_scope_adapter', None)
        if not required or not callable(adapter):
            return False
        scopes = adapter(request)
        return bool(scopes) and has_object_permission(request.user, required, scopes=scopes)

    def has_object_permission(self, request, view, obj):
        adapter = getattr(view, 'object_scope_adapter', None)
        required = getattr(view, 'required_permissions', {}).get(request.method)
        if not required or not callable(adapter):
            return False
        return has_object_permission(request.user, required, scopes=adapter(obj))
