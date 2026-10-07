"""Scoped inspection only; mutations use the versioned admission command interface."""
from django.contrib import admin
from . import models as m
from .policies import scoped, allowed


class DomainAdmin(admin.ModelAdmin):
    actions = None
    list_per_page = 25

    def get_queryset(self, request):
        return scoped(self.model, request.user)

    def has_view_permission(self, request, obj=None):
        return allowed(request.user, 'view', self.model) and (obj is None or scoped(self.model,request.user).filter(pk=obj.pk).exists())

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        fields=[f.name for f in self.model._meta.fields]
        if not allowed(request.user,'sensitive'):
            fields=[f for f in fields if f not in ('date_of_birth','primary_email','primary_phone','social_category','caste','sub_caste','remarks')]
        return fields


@admin.register(m.AdmissionApplicant)
class ApplicantAdmin(DomainAdmin):
    list_display=('admission_applicant_id','display_name','institution','version')
    search_fields=('display_name',)


@admin.register(m.AdmissionApplication)
class ApplicationAdmin(DomainAdmin):
    list_display=('application_number','application_status','eligibility_status','version')
    search_fields=('application_number',)
    list_filter=('application_status','eligibility_status')


@admin.register(m.StudentProgrammeEnrolment)
class EnrolmentAdmin(DomainAdmin):
    list_display=('enrolment_id','enrolment_status','admission_date','version')
    list_filter=('enrolment_status',)


@admin.register(m.EnrolmentStatusHistory)
class HistoryAdmin(DomainAdmin):
    list_display=('enrolment_id','old_status','new_status','effective_date','sequence_number')


@admin.register(m.AdmissionAudit, m.FeeClearance)
class SupportAdmin(DomainAdmin):
    def get_queryset(self,request):
        return self.model.objects.all() if request.user.is_active and request.user.is_superuser else self.model.objects.none()

    def has_view_permission(self,request,obj=None):
        return request.user.is_active and request.user.is_superuser
