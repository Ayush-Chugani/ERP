"""Scoped inspection; mutations use the service-backed activity console."""

from django.contrib import admin
from rest_framework.exceptions import APIException

from .models import StaffAward
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


@admin.register(StaffAward)
class StaffAwardAdmin(ReadOnlyAdmin):
    list_display = (
        "staff_activity_id",
        "award_category",
        "award_name",
    )
    list_filter = ("award_category", "award_date", "awarding_organization")
    list_select_related = ("staff_activity", "award_category")
    search_fields = ("award_name", "award_reference_number")

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


from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import transaction

from apps.identity_access.audit import record
from apps.staff_profile.models import AwardCategory

from .permissions import require


@admin.register(AwardCategory)
class AwardCategoryAdmin(admin.ModelAdmin):
    list_display = ("category_code", "category_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("category_code", "category_name")
    actions = None

    def allowed(self, request):
        try:
            require(request.user, "MASTER", "UPDATE")
            return True
        except APIException:
            return False

    def has_module_permission(self, request):
        return self.allowed(request)

    def has_view_permission(self, request, obj=None):
        return self.allowed(request)

    def has_add_permission(self, request):
        return self.allowed(request)

    def has_change_permission(self, request, obj=None):
        return self.allowed(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        rows = super().get_queryset(request)
        return rows if self.allowed(request) else rows.none()

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not self.allowed(request):
            raise DjangoPermissionDenied()
        if change:
            AwardCategory.objects.select_for_update().get(pk=obj.pk)
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record(
            actor=request.user,
            module="AWARDS",
            action="UPDATE" if change else "CREATE",
            entity=obj,
            details={"fields": list(form.changed_data)},
        )
