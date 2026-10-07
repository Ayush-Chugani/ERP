"""Scoped inspection; mutations use the service-backed internship console."""

from django.contrib import admin
from rest_framework.exceptions import APIException

from .models import FacultyInternship
from .permissions import activity_scope


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return self.has_view_permission(request)


@admin.register(FacultyInternship)
class FacultyInternshipAdmin(ReadOnlyAdmin):
    list_display = (
        "staff_activity_id",
        "organization",
        "internship_title",
    )
    list_select_related = ("staff_activity", "organization")
    search_fields = ("internship_title", "internship_domain")

    def get_queryset(self, request):
        try:
            return (
                super()
                .get_queryset(request)
                .filter(
                    activity_scope(request.user),
                    staff_activity__deleted_at__isnull=True,
                )
            )
        except APIException:
            return super().get_queryset(request).none()

    def has_view_permission(self, request, obj=None):
        return (
            self.get_queryset(request).filter(pk=obj.pk).exists()
            if obj
            else self.get_queryset(request).exists()
        )
