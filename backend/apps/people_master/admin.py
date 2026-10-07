from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db import transaction
from django import forms
from django.db import models
from django.db.models import Q
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from rest_framework.exceptions import APIException
from . import models as m
from .catalogue import FIELDS, SHARED, CONFIDENTIAL, RESTRICTED
from .permissions import scoped, related, permitted
from .services import execute, Command, version, audit
from .integrations.upstream import grants


class GovernedForm(forms.ModelForm):
    expected_version = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["expected_version"] = version(self.instance)


class ReasonActionForm(ActionForm):
    reason = forms.CharField(
        max_length=250, required=False, label="Reason (no personal details)"
    )


class GovernedAdmin(admin.ModelAdmin):
    form = GovernedForm
    actions = ["activate_records", "deactivate_records"]
    action_form = ReasonActionForm
    list_per_page = 25

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        return (*fields, "competencies_link") if self.model is m.Employee else fields

    @admin.display(description="Competencies")
    def competencies_link(self, obj):
        return format_html(
            '<a href="/#/people/competencies?employee_id={}">Open competency editor</a>',
            obj.pk,
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if self.model not in (m.Student, m.Employee) and not hasattr(
            self.model, "is_active"
        ):
            return {}
        if self.model in (m.Student, m.Employee):
            actions.pop("deactivate_records", None)
        return actions

    def lifecycle(self, request, queryset, active):
        reason = request.POST.get("reason", "").strip()
        if not reason:
            self.message_user(request, "A reason is required.", messages.ERROR)
            return
        try:
            with transaction.atomic():
                for obj in queryset:
                    root = isinstance(obj, (m.Student, m.Employee))
                    execute(
                        Command(
                            self.model,
                            request.user,
                            {"status": "ACTIVE"} if root else {},
                            obj.pk,
                            "status"
                            if root
                            else "activate"
                            if active
                            else "deactivate",
                            version(obj),
                            reason,
                            "admin",
                        )
                    )
        except APIException:
            self.message_user(
                request,
                "The entire action was rolled back: one or more records are not eligible.",
                messages.ERROR,
            )
        else:
            self.message_user(request, "Selected records updated and audited.")

    @admin.action(description="Activate selected records (requires reason/readiness)")
    def activate_records(self, request, queryset):
        self.lifecycle(request, queryset, True)

    @admin.action(description="Deactivate selected reference records (requires reason)")
    def deactivate_records(self, request, queryset):
        self.lifecycle(request, queryset, False)

    def get_queryset(self, request):
        return related(scoped(self.model, request.user))

    def has_view_permission(self, request, obj=None):
        return permitted(request.user, self.model) and (
            obj is None or scoped(self.model, request.user).filter(pk=obj.pk).exists()
        )

    def has_add_permission(self, request):
        return permitted(request.user, self.model, "add") and (
            self.model not in SHARED or request.user.is_superuser
        )

    def has_change_permission(self, request, obj=None):
        return (
            permitted(request.user, self.model, "change")
            and (self.model not in SHARED or request.user.is_superuser)
            and (
                obj is None
                or scoped(self.model, request.user, "change").filter(pk=obj.pk).exists()
            )
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        hidden = (
            CONFIDENTIAL
            if not permitted(request.user, self.model, "confidential")
            else set()
        ) | (
            RESTRICTED
            if not permitted(request.user, self.model, "restricted")
            else set()
        )
        return [
            self.model._meta.get_field(n[:-3] if n.endswith("_id") else n).name
            for n in FIELDS[self.model]
            if n not in hidden
        ] + ["expected_version"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        target = db_field.remote_field.model
        if target in FIELDS:
            kwargs["queryset"] = scoped(target, request.user)
        elif target._meta.app_label == "organization" and not request.user.is_superuser:
            rows = list(grants(request.user))
            condition = Q(pk__in=[])
            name = target._meta.model_name
            for grant in rows:
                part = (
                    Q(pk=grant.membership.institution_id)
                    if name == "institution"
                    else Q(institution_id=grant.membership.institution_id)
                    if name == "campus"
                    else Q(campus__institution_id=grant.membership.institution_id)
                )
                if name == "campus" and grant.campus_id:
                    part &= Q(pk=grant.campus_id)
                if name == "department":
                    if grant.campus_id:
                        part &= Q(campus_id=grant.campus_id)
                    if grant.department_id:
                        part &= Q(pk=grant.department_id)
                key = {
                    "institution": "institutions",
                    "campus": "campuses",
                    "department": "departments",
                }.get(name)
                if key in grant.record_limits:
                    part &= Q(pk__in=grant.record_limits[key])
                condition |= part
            query = target.objects.filter(condition)
            kwargs["queryset"] = query
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        values = {}
        for name in FIELDS[self.model]:
            fieldname = name[:-3] if name.endswith("_id") else name
            if fieldname in form.cleaned_data:
                value = form.cleaned_data[fieldname]
                values[name] = value.pk if isinstance(value, models.Model) else value
        saved = execute(
            Command(
                self.model,
                request.user,
                values,
                obj.pk if change else None,
                expected_version=form.cleaned_data.get("expected_version"),
                source="admin",
            )
        )
        obj.pk = saved.pk
        obj._state = saved._state

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            response = super().changeform_view(
                request, object_id, form_url, extra_context
            )
            if request.method == "GET" and object_id and response.status_code == 200:
                obj = self.get_queryset(request).filter(pk=object_id).first()
                if obj:
                    audit(obj, request.user, "read", {}, source="admin")
            return response
        except APIException:
            self.message_user(
                request,
                "Save rejected by scope or domain validation. Reload and review the record.",
                messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if response.status_code == 200:
            m.PeopleAudit.objects.create(
                actor=request.user,
                resource=self.model._meta.db_table,
                record_key="list",
                action="read",
                source="admin",
            )
        return response


for model in FIELDS:
    if model is m.EmployeeCompetency:
        continue  # Django 5.2 admin rejects composite PKs.
    names = [
        f.name
        for f in model._meta.fields
        if f.name
        in (
            "student_number",
            "employee_number",
            "display_name",
            "type_code",
            "type_name",
            "category_code",
            "category_name",
            "source_code",
            "source_name",
            "agency_code",
            "agency_name",
            "designation_code",
            "designation_name",
        )
    ]
    attrs = {
        "list_display": tuple([model._meta.pk.name] + names),
        "search_fields": tuple(names),
        "list_filter": tuple(
            f.name
            for f in model._meta.fields
            if f.name in ("is_active", "student_status", "employment_status")
        ),
    }
    admin.site.register(model, type(model.__name__ + "Admin", (GovernedAdmin,), attrs))


@admin.register(m.PeopleAudit)
class AuditAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "actor",
        "resource",
        "record_key",
        "action",
        "source",
        "outcome",
    )
    list_filter = ("resource", "action", "source")
    actions = None

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("actor", "institution")
            if self.has_view_permission(request)
            else super().get_queryset(request).none()
        )
