from django.contrib import admin
from . import models as m


class InspectOnly(admin.ModelAdmin):
    actions = None

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in [m.FacultyAssignment, m.TimetablePlan, m.TimetableRevision, m.TimetableSession,
    m.PublishedOccurrence, m.OccurrenceException, m.TimetableAudit, m.OutboxEvent,
    m.SolverJob, m.SchedulingPolicy, m.ResourceAvailability]:
    admin.site.register(model, InspectOnly)
