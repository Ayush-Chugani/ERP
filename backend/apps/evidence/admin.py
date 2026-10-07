from django.contrib import admin
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import APIException

from apps.identity_access.audit import record

from . import models as m
from . import permissions as p
from . import selectors


class ReadOnly(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_view_permission(self, request, obj=None):
        rows = self.get_queryset(request)
        return rows.filter(pk=obj.pk).exists() if obj else rows.exists()

    def authorized_documents(self, request, resource="DOCUMENT"):
        live = (
            selectors.documents(request.user, resource=resource).order_by().values("pk")
        )
        deleted = (
            selectors.documents(request.user, deleted=True, resource=resource)
            .order_by()
            .values("pk")
        )
        return m.EvidenceDocument.all_objects.filter(
            Q(pk__in=live) | Q(pk__in=deleted)
        ).values("pk")


@admin.register(m.EvidenceDocument)
class EvidenceDocumentAdmin(ReadOnly):
    list_display = (
        "evidence_document_id",
        "document_title",
        "current_version_number",
        "is_active",
    )
    list_filter = (
        "verification_status",
        "approval_status",
        "document_type",
        "expiry_date",
    )
    search_fields = ("document_title", "certificate_document_number")

    def get_queryset(self, request):
        try:
            return m.EvidenceDocument.all_objects.filter(
                pk__in=self.authorized_documents(request)
            ).select_related(
                "document_type",
                "confidentiality_level",
                "verification_status",
                "approval_status",
            )
        except APIException:
            return m.EvidenceDocument.all_objects.none()


@admin.register(m.EvidenceDocumentVersion)
class EvidenceVersionAdmin(ReadOnly):
    list_display = (
        "evidence_document_version_id",
        "evidence_document_id",
        "version_number",
        "is_current",
        "uploaded_at",
    )
    exclude = ("file_object",)

    def get_queryset(self, request):
        try:
            return (
                super()
                .get_queryset(request)
                .filter(
                    evidence_document_id__in=self.authorized_documents(
                        request, "HISTORY"
                    )
                )
            )
        except APIException:
            return super().get_queryset(request).none()


@admin.register(m.EvidenceDocumentAudit)
class EvidenceAuditAdmin(ReadOnly):
    list_display = (
        "evidence_document_audit_id",
        "evidence_document_id",
        "action_code",
        "performed_by_user_id",
        "performed_at",
    )
    list_filter = ("action_code", "performed_at")
    search_fields = ("ip_address",)

    def get_queryset(self, request):
        try:
            return (
                super()
                .get_queryset(request)
                .filter(
                    evidence_document_id__in=self.authorized_documents(request, "AUDIT")
                )
            )
        except APIException:
            return super().get_queryset(request).none()


@admin.register(m.EvidenceTag)
class EvidenceTagAdmin(admin.ModelAdmin):
    list_display = ("tag_code", "tag_name", "is_active")
    search_fields = ("tag_code", "tag_name")
    list_filter = ("is_active",)
    actions = None

    def allowed(self, request):
        try:
            p.require(request.user, "TAG", "UPDATE")
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
        return (
            super().get_queryset(request)
            if self.allowed(request)
            else super().get_queryset(request).none()
        )

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not self.allowed(request):
            raise DjangoPermissionDenied()
        if change:
            m.EvidenceTag.objects.select_for_update().get(pk=obj.pk)
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record(
            actor=request.user,
            module="EVIDENCE",
            action="UPDATE" if change else "CREATE",
            entity=obj,
            details={"fields": list(form.changed_data)},
        )
