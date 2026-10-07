from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db import transaction
from django.http import HttpResponseRedirect
from rest_framework.exceptions import APIException
from .models import AcademicYear, AcademicTerm, Semester, TimeSlot, CalendarAudit
from .policies import scoped, can_create, permitted, campuses
from .services import FIELDS, TRANSITIONS, save_record, transition


class TransitionActionForm(ActionForm):
    reason = forms.CharField(max_length=250, required=False, label='Reason for close/reopen')


class CalendarAdmin(admin.ModelAdmin):
    action_form = TransitionActionForm
    list_per_page = 25
    actions = ['activate', 'close', 'reopen', 'open_registration', 'deactivate']

    def get_queryset(self, request):
        rows = scoped(self.model, request.user)
        if self.model is AcademicTerm:
            rows = rows.select_related('academic_year')
        if self.model is TimeSlot:
            rows = rows.select_related('campus__institution')
        return rows

    def has_view_permission(self, request, obj=None):
        return scoped(self.model, request.user).filter(pk=obj.pk).exists() if obj else permitted(request.user, self.model, 'view')

    def has_add_permission(self, request):
        return can_create(request.user, self.model)

    def has_change_permission(self, request, obj=None):
        return scoped(self.model, request.user, action='change').filter(pk=obj.pk).exists() if obj else permitted(request.user, self.model, 'change')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        lifecycle = ['is_active'] if self.model is TimeSlot else ['status'] if self.model in (AcademicYear, AcademicTerm) else []
        if obj and getattr(obj, 'status', None) == 'CLOSED':
            return [f.name for f in self.model._meta.fields]
        if obj:
            lifecycle += [f.name for f in self.model._meta.fields if f.is_relation]
        return lifecycle

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'campus':
            kwargs['queryset'] = campuses(request.user, write=True).filter(is_active=True, institution__is_active=True, institution__university__is_active=True)
        if db_field.name == 'academic_year':
            kwargs['queryset'] = scoped(AcademicYear, request.user).exclude(status='CLOSED')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        values = {name:getattr(obj, name) for name in FIELDS[self.model]}
        saved = save_record(self.model, values, actor=request.user, pk=obj.pk if change else None)
        obj.pk = saved.pk
        obj._state = saved._state

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            with transaction.atomic():
                return super().changeform_view(request, object_id, form_url, extra_context)
        except APIException as error:
            self.message_user(request, str(error.detail), messages.ERROR)
            return HttpResponseRedirect(request.path)

    def get_actions(self, request):
        actions = super().get_actions(request)
        return {name:value for name,value in actions.items() if name in TRANSITIONS.get(self.model, {}) and permitted(request.user, self.model, name)}

    def perform_transition(self, request, queryset, name):
        try:
            with transaction.atomic():
                for pk in queryset.order_by('pk').values_list('pk', flat=True):
                    transition(self.model, pk, name, actor=request.user, reason=request.POST.get('reason', ''))
        except APIException as error:
            self.message_user(request, f'No changes committed: {error.detail}', messages.ERROR)
        else:
            self.message_user(request, 'Calendar transition completed.', messages.SUCCESS)

    @admin.action(description='Activate selected records')
    def activate(self, request, queryset):
        self.perform_transition(request, queryset, 'activate')

    @admin.action(description='Close selected periods (reason required)')
    def close(self, request, queryset):
        self.perform_transition(request, queryset, 'close')

    @admin.action(description='Reopen selected periods (reason required)')
    def reopen(self, request, queryset):
        self.perform_transition(request, queryset, 'reopen')

    @admin.action(description='Open registration for selected terms')
    def open_registration(self, request, queryset):
        self.perform_transition(request, queryset, 'open_registration')

    @admin.action(description='Deactivate selected slots')
    def deactivate(self, request, queryset):
        self.perform_transition(request, queryset, 'deactivate')


for model in FIELDS:
    display = [model._meta.pk.name, *FIELDS[model]]
    if model in (AcademicYear, AcademicTerm):
        display.append('status')
    if model is TimeSlot:
        display.append('is_active')
    config = type(model.__name__ + 'Admin', (CalendarAdmin,), {
        'list_display':display,
        'search_fields': ['year_code'] if model is AcademicYear else ['term_code','term_name'] if model is AcademicTerm else ['semester_name'] if model is Semester else ['slot_code'],
        'list_filter': ['status'] if model in (AcademicYear, AcademicTerm) else ['is_active','is_break'] if model is TimeSlot else [],
    })
    admin.site.register(model, config)


@admin.register(CalendarAudit)
class CalendarAuditAdmin(admin.ModelAdmin):
    list_display = ['timestamp','actor','institution','resource','record_id','action']
    list_filter = ['resource','action']
    search_fields = ['correlation_id']
    list_select_related = ['actor','institution']
    readonly_fields = [f.name for f in CalendarAudit._meta.fields]
    actions = None

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def get_queryset(self, request):
        query = super().get_queryset(request)
        return query if self.has_view_permission(request) else query.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
