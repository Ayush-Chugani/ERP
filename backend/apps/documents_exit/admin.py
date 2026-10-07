from django.contrib import admin

from . import models as m
from . import permissions as p
from . import selectors as q


class ReadOnly(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(m.StudentDocument)
class DocumentAdmin(ReadOnly):
    list_display = ("student_document_id", "document_type_id", "verification_status")
    fields = list_display

    def has_view_permission(self, request, obj=None):
        return p.can(request.user, "view_documents")

    def get_queryset(self, request):
        return q.documents(request.user)


@admin.register(m.CertificateRequest)
class CertificateAdmin(ReadOnly):
    list_display = ("request_number", "request_status", "requested_at", "issued_at")
    fields = list_display

    def has_view_permission(self, request, obj=None):
        return p.can(request.user, "view_certificates")

    def get_queryset(self, request):
        return q.certificates(request.user)


@admin.register(m.StudentExit)
class ExitAdmin(ReadOnly):
    list_display = ("student_exit_id", "exit_type", "exit_date")
    fields = list_display

    def has_view_permission(self, request, obj=None):
        return p.can(request.user, "view_exit")

    def get_queryset(self, request):
        return q.exits(request.user)


# File keys/URLs and protected audit reasons are never generic admin content.
