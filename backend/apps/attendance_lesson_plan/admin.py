from django.contrib import admin
from . import models as m
class InspectOnly(admin.ModelAdmin):
    def has_module_permission(self,request):return request.user.is_active and request.user.is_superuser
    def has_view_permission(self,request,obj=None):return self.has_module_permission(request)
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
for model in [m.ClassSession,m.PolicyRevision,m.StudentAttendance,m.CorrectionRequest,m.LessonRevision,m.TopicCoverage,m.AuditEvent,m.AttendanceStatus]:
    admin.site.register(model,InspectOnly)
