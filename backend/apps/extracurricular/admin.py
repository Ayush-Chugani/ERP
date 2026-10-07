"""Scoped inspection; mutations use the service-backed activity console."""

from django.contrib import admin
from rest_framework.exceptions import APIException

from .models import ExtracurricularActivity
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


@admin.register(ExtracurricularActivity)
class ExtracurricularActivityAdmin(ReadOnlyAdmin):
    list_display = (
        "staff_activity_id",
        "extracurricular_category",
        "event_name",
    )
    list_filter = ("extracurricular_category",)
    list_select_related = ("staff_activity", "extracurricular_category")
    search_fields = ("event_name", "award_recognition")

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
