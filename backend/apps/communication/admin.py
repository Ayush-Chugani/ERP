from django.contrib import admin

from .models import Announcement, AnnouncementType


class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    actions = None


@admin.register(Announcement)
class AnnouncementAdmin(ReadOnly):
    list_display = (
        "announcement_id",
        "title",
        "approval_status",
        "publish_from",
        "publish_to",
    )
    list_filter = ("approval_status", "audience_type")
    search_fields = ("title",)


admin.site.register(AnnouncementType, ReadOnly)
