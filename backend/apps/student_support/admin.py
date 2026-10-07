from django.contrib import admin
from rest_framework.exceptions import PermissionDenied

from . import models as m
from . import permissions as p


class ReadOnly(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(m.MentorAssignment)
class MentorAdmin(ReadOnly):
    list_display = (
        "mentor_assignment_id",
        "student_id",
        "employee_id",
        "start_date",
        "end_date",
        "assignment_status",
    )
    list_filter = ("assignment_status",)

    def has_view_permission(self, request, obj=None):
        return p.can(request.user, "manage_mentor_assignments")

    def get_queryset(self, request):
        return p.assignments(request.user, "manage_mentor_assignments")


@admin.register(m.CounsellingSession)
class SessionAdmin(ReadOnly):
    list_display = (
        "counselling_session_id",
        "session_date",
        "session_status",
        "confidentiality_level",
    )
    fields = (
        "counselling_session_id",
        "session_date",
        "session_status",
        "confidentiality_level",
    )

    def has_view_permission(self, request, obj=None):
        return any(
            p.can(request.user, "view_counselling_" + x.lower())
            for x in ("NORMAL", "RESTRICTED", "HIGHLY_RESTRICTED")
        )

    def get_queryset(self, request):
        return p.sessions(request.user).defer("observations", "action_plan")


@admin.register(m.Grievance)
class GrievanceAdmin(ReadOnly):
    list_display = ("grievance_number", "submitted_at", "status", "priority")
    fields = ("grievance_number", "submitted_at", "status", "priority")

    def has_view_permission(self, request, obj=None):
        return p.can(request.user, "view_grievance_queue")

    def get_queryset(self, request):
        return p.grievances(request.user, "view_grievance_queue").defer(
            "subject", "description", "resolution"
        )


@admin.register(m.GrievanceCategory)
class CategoryAdmin(ReadOnly):
    list_display = ("category_code", "category_name", "is_active")

    def has_view_permission(self, request, obj=None):
        try:
            p.category_admin(request.user)
            return True
        except PermissionDenied:
            return False


# The staff application calls services. No generic admin writer or action-history editor.
