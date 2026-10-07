"""Scoped inspection; mutations use the service-backed activity console."""

from django.contrib import admin
from rest_framework.exceptions import APIException

from .models import StaffProfessionalContribution
from .permissions import activity_scope
from .selectors import student_read_scope


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return self.has_view_permission(request)


@admin.register(StaffProfessionalContribution)
class StaffProfessionalContributionAdmin(ReadOnlyAdmin):
    list_display = (
        "staff_activity_id",
        "professional_contribution_type",
        "title_topic",
    )
    list_filter = (
        "professional_contribution_type",
        "contribution_date",
        "organization",
    )
    list_select_related = ("staff_activity", "professional_contribution_type")
    search_fields = ("title_topic", "appointment_reference_number")

    def get_queryset(self, request):
        try:
            return (
                super()
                .get_queryset(request)
                .filter(
                    activity_scope(request.user),
                    student_read_scope(request.user),
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

from apps.staff_profile.models import ProfessionalContributionType

from .observability import record
from .permissions import require


@admin.register(ProfessionalContributionType)
class ProfessionalContributionTypeAdmin(admin.ModelAdmin):
    list_display = ("contribution_code", "contribution_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("contribution_code", "contribution_name")
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
            ProfessionalContributionType.objects.select_for_update().get(pk=obj.pk)
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record(
            actor=request.user,
            module="PROFESSIONAL_CONTRIBUTIONS",
            action="UPDATE" if change else "CREATE",
            entity=obj,
            details={"fields": list(form.changed_data)},
        )
