from django import forms
from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponseRedirect
from rest_framework.exceptions import APIException
from apps.core.fields import ReferenceTextField
from .resources import RESOURCES
from .selectors import related, is_available, available
from .services import write_reference


class ReferenceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.instance._meta.fields:
            if not field.is_relation or field.name not in self.fields:
                continue
            queryset = available(field.related_model.objects.all())
            if self.instance.pk:
                # Keep the stored historical choice visible, including ancestors.
                queryset = queryset | field.related_model.objects.filter(pk=getattr(self.instance, field.attname))
            self.fields[field.name].queryset = related(queryset)
            self.fields[field.name].label_from_instance = self.parent_label

    @staticmethod
    def parent_label(obj):
        names = next(row[2] for row in RESOURCES if row[0] is type(obj))
        label = next(name for name in names if name.endswith('_name'))
        suffix = '' if is_available(obj) else ' (unavailable)'
        return f'{getattr(obj, label)} [{obj.pk}]{suffix}'

    def clean(self):
        cleaned = super().clean()
        original = type(self.instance).objects.filter(pk=self.instance.pk).first() if self.instance.pk else None
        for field in self.instance._meta.fields:
            if not field.is_relation or field.name not in cleaned:
                continue
            parent = cleaned[field.name]
            unchanged = original is not None and getattr(original, field.attname) == getattr(parent, 'pk', None)
            if parent is not None and not unchanged and not is_available(parent):
                self.add_error(field.name, 'New assignments require an active parent and active ancestors.')
        return cleaned


class ReferenceAdmin(admin.ModelAdmin):
    form = ReferenceForm
    actions = None
    list_per_page = 25

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if isinstance(db_field, ReferenceTextField) and field is not None:
            # Normalize before form length/required validators, matching the API.
            field.to_python = db_field.to_python
        return field

    def permitted(self, request, operation):
        return bool(request.user.is_active and
                    request.user.has_perm('common_reference.maintain_reference') and
                    request.user.has_perm(f'common_reference.{operation}_{self.model._meta.model_name}'))

    def has_view_permission(self, request, obj=None):
        return self.permitted(request, 'view')

    def has_add_permission(self, request):
        return self.permitted(request, 'add')

    def has_change_permission(self, request, obj=None):
        return self.permitted(request, 'change')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return related(super().get_queryset(request))

    def save_model(self, request, obj, form, change):
        values = {name: getattr(obj, name) for name in self.fields}
        saved = write_reference(self.model, values, obj.pk if change else None,
                                actor=request.user, source='admin')
        obj.pk = saved.pk
        obj._state = saved._state
        for field in obj._meta.concrete_fields:
            if not field.generated:
                setattr(obj, field.attname, getattr(saved, field.attname))

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            # Cover form validation, the shared service, and Django's admin log
            # with one transaction and the same catalogue lock as API writes.
            with transaction.atomic():
                if request.method == 'POST':
                    ContentType.objects.select_for_update().get(app_label='common_reference', model='country')
                return super().changeform_view(request, object_id, form_url, extra_context)
        except APIException as exc:
            # Expected concurrent conflicts are safe messages after rollback.
            self.message_user(request, str(exc.detail), level=messages.ERROR)
            return HttpResponseRedirect(request.path)


for model, path, writable, parent, label in RESOURCES:
    fields = tuple(model._meta.get_field(name).name for name in writable)
    text_fields = tuple(name for name in writable if not name.endswith('_id') and name not in ('is_active', 'requires_verification'))
    config = {
        'fields': fields,
        'list_display': (model._meta.pk.name, *writable),
        'search_fields': text_fields,
        'list_filter': ('is_active',) + ((parent,) if parent else ()),
        'ordering': (text_fields[0], model._meta.pk.name),
    }
    admin.site.register(model, type(model.__name__ + 'Admin', (ReferenceAdmin,), config))
