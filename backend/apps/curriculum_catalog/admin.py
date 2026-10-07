from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from rest_framework.exceptions import APIException
from .models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
    CurriculumAudit,
)
from .policies import scoped, related, permitted
from .services import FIELDS, Command, execute, version
from .integrations.upstream import organization_rows


class GovernedForm(forms.ModelForm):
    expected_version = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["expected_version"] = version(self.instance)


class TransitionForm(ActionForm):
    reason = forms.CharField(required=False, max_length=250)


class GovernedAdmin(admin.ModelAdmin):
    form = GovernedForm
    action_form = TransitionForm
    actions = ["activate", "deactivate", "retire"]
    list_per_page = 25

    def get_queryset(self, request):
        return related(scoped(self.model, request.user))

    def has_view_permission(self, request, obj=None):
        return (
            scoped(self.model, request.user).filter(pk=obj.pk).exists()
            if obj
            else permitted(request.user, self.model, "view")
        )

    def has_add_permission(self, request):
        return permitted(request.user, self.model, "add")

    def has_change_permission(self, request, obj=None):
        return (
            scoped(self.model, request.user, "change").filter(pk=obj.pk).exists()
            if obj
            else permitted(request.user, self.model, "change")
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj and (
            isinstance(obj, CurriculumScheme)
            and obj.status != "DRAFT"
            or isinstance(obj, CurriculumCourse)
            and obj.curriculum_scheme.status != "DRAFT"
        ):
            return [f.name for f in self.model._meta.fields]
        fields = [name for name in ("is_active", "status") if hasattr(self.model, name)]
        if obj:
            fields += [
                name[:-3]
                for name in (
                    "owning_department_id",
                    "programme_id",
                    "curriculum_scheme_id",
                )
                if name in FIELDS[self.model]
            ]
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kinds = {
            "owning_department": "departments",
            "programme": "programmes",
            "specialization": "specializations",
        }
        if db_field.name in kinds:
            kwargs["queryset"] = organization_rows(
                kinds[db_field.name], request.user, write=True
            ).filter(is_active=True)
        elif db_field.related_model in FIELDS:
            kwargs["queryset"] = scoped(db_field.related_model, request.user)
        elif db_field.name == "semester":
            # Calendar model import remains confined to its public contract.
            from .integrations.admin_calendar import semester_queryset

            kwargs["queryset"] = semester_queryset(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        result = execute(
            Command(
                self.model,
                request.user,
                {name: getattr(obj, name) for name in FIELDS[self.model]},
                obj.pk if change else None,
                expected_version=form.cleaned_data.get("expected_version"),
            )
        )
        obj.pk = result.pk
        obj._state = result._state

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            with transaction.atomic():
                return super().changeform_view(
                    request, object_id, form_url, extra_context
                )
        except APIException as error:
            self.message_user(request, str(error.detail), messages.ERROR)
            return HttpResponseRedirect(request.path)

    def get_actions(self, request):
        permitted_names = (
            {"activate", "deactivate"}
            if self.model in (CourseCategory, CourseCatalog)
            else {"activate", "retire"}
            if self.model is CurriculumScheme
            else set()
        )
        return {
            name: action
            for name, action in super().get_actions(request).items()
            if name in permitted_names and permitted(request.user, self.model, name)
        }

    def perform_action(self, request, queryset, name):
        try:
            with transaction.atomic():
                from django.contrib.contenttypes.models import ContentType

                ContentType.objects.select_for_update().get(
                    app_label="organization", model="university"
                )
                rows = list(queryset.order_by("pk"))
                # Eligibility preflight before the first write; services recheck state.
                if any(
                    not scoped(self.model, request.user, name)
                    .filter(pk=row.pk)
                    .exists()
                    for row in rows
                ):
                    self.message_user(
                        request,
                        "No records changed: selection contains unauthorized records.",
                        messages.ERROR,
                    )
                    return
                for row in rows:
                    execute(
                        Command(
                            self.model,
                            request.user,
                            pk=row.pk,
                            action=name,
                            expected_version=version(row),
                            reason=request.POST.get("reason", ""),
                        )
                    )
        except APIException as error:
            self.message_user(
                request, "No records changed: " + str(error.detail), messages.ERROR
            )
        else:
            self.message_user(request, "All selected records changed successfully.")

    @admin.action(description="Activate selected records (reason required)")
    def activate(self, request, queryset):
        self.perform_action(request, queryset, "activate")

    @admin.action(description="Deactivate selected records (reason required)")
    def deactivate(self, request, queryset):
        self.perform_action(request, queryset, "deactivate")

    @admin.action(description="Retire selected schemes (reason required)")
    def retire(self, request, queryset):
        self.perform_action(request, queryset, "retire")


for model in (CourseCategory, CourseCatalog, CurriculumScheme, CurriculumCourse):
    search = {
        CourseCategory: ["category_code", "category_name"],
        CourseCatalog: ["course_code", "course_title"],
        CurriculumScheme: ["scheme_code", "scheme_name"],
        CurriculumCourse: ["course__course_code"],
    }[model]
    displays = [
        model._meta.pk.name,
        *[name for name in FIELDS[model] if not name.endswith("_id")][:4],
    ]
    attrs = {
        "list_display": displays,
        "search_fields": search,
        "list_filter": ["status"]
        if model is CurriculumScheme
        else ["is_active"]
        if model in (CourseCatalog, CourseCategory)
        else ["is_mandatory"],
    }
    if model is CourseCatalog:

        def prerequisites(self, obj):
            return format_html(
                '<a href="/#/curriculum/prerequisites?course_id={}">Manage prerequisites in curriculum workspace</a>',
                obj.pk,
            )

        attrs["prerequisites"] = prerequisites
        attrs["list_display"] = displays + ["prerequisites"]
    admin.site.register(model, type(model.__name__ + "Admin", (GovernedAdmin,), attrs))


@admin.register(CurriculumAudit)
class AuditAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "actor",
        "institution",
        "resource",
        "record_key",
        "action",
    ]
    list_filter = ["resource", "action"]
    search_fields = ["correlation_id", "record_key"]
    readonly_fields = [f.name for f in CurriculumAudit._meta.fields]
    list_select_related = ["actor", "institution"]
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
