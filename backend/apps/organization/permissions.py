from rest_framework.permissions import BasePermission

class OrganizationAccess(BasePermission):
    """Authentication gate; selectors/services enforce actual scope per action."""
    def has_permission(self,request,view):
        return bool(request.user.is_authenticated and request.user.is_active)
    def has_object_permission(self,request,view,obj):
        from .selectors import scoped
        write=view.action not in ('retrieve','list')
        return scoped(type(obj),request.user,write=write).filter(pk=obj.pk).exists()
