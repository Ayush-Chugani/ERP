"""Scoped inspection; mutations use the service-backed conference console."""

from django.contrib import admin
from rest_framework.exceptions import APIException

from .models import ConferenceActivity, ConferenceEvent
from .permissions import activity_scope, require


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return self.has_view_permission(request)


@admin.register(ConferenceEvent)
class ConferenceEventAdmin(ReadOnlyAdmin):
    list_display = ("conference_title", "start_date", "end_date", "is_active")
    search_fields = ("conference_title", "conference_edition")
    list_filter = ("is_active", "event_mode")

    def has_view_permission(self, request, obj=None):
        try:
            require(request.user, "EVENT", "READ")
            return True
        except APIException:
            return False


@admin.register(ConferenceActivity)
class ConferenceActivityAdmin(ReadOnlyAdmin):
    list_display = (
        "staff_activity_id",
        "conference_event",
        "paper_title",
        "presentation_title",
    )
    list_select_related = ("staff_activity", "conference_event")
    search_fields = ("paper_title", "presentation_title", "doi")

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
