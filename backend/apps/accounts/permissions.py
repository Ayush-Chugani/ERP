from rest_framework.permissions import BasePermission

class IsAdminOrTeacher(BasePermission):
    """Global starter bundles only; future domain views must also check scope."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.is_active and (
            user.is_superuser or user.groups.filter(name__in=["Admin", "Teacher"]).exists()))

class ReferencePermissions(BasePermission):
    actions = {"list":"view", "retrieve":"view", "metadata":"view", "create":"add", "update":"change",
               "partial_update":"change", "destroy":"delete", "activate":"change", "deactivate":"change"}
    methods = {"GET":"view", "HEAD":"view", "OPTIONS":"view", "POST":"add", "PUT":"change", "PATCH":"change", "DELETE":"delete"}
    def has_permission(self, request, view):
        user=request.user
        if not user.is_authenticated or not user.is_active:
            return False
        model=getattr(view, "permission_model", None)
        action=getattr(view, "action", None)
        operation=self.actions.get(action) if action else self.methods.get(request.method)
        if model is None or operation is None:
            return False
        permission=f"{model._meta.app_label}.{operation}_{model._meta.model_name}"
        return user.has_perm(permission) and (operation == "view" or user.has_perm("common_reference.maintain_reference"))
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
