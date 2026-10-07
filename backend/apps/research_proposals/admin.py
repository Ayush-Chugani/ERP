"""Scoped inspection; mutations use the service-backed proposal console."""

from django.contrib import admin
from rest_framework.exceptions import APIException

from .models import ResearchProposal
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


@admin.register(ResearchProposal)
class ResearchProposalAdmin(ReadOnlyAdmin):
    list_display = (
        "staff_activity_id",
        "funding_agency",
        "proposal_title",
    )
    list_filter = ("research_status", "funding_type")
    list_select_related = ("staff_activity", "funding_agency")
    search_fields = ("proposal_title", "research_domain")

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
