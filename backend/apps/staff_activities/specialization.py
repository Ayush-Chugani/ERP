"""Validate specialization exclusivity under the caller's StaffActivity row lock."""

from django.apps import apps
from django.core.exceptions import ValidationError

from .models import StaffActivity


def ensure_exclusive(parent, expected_model):
    if not parent.pk:
        return
    for model in apps.get_models():
        field = model._meta.pk
        if model is expected_model or model._meta.proxy or not field.one_to_one:
            continue
        if (
            field.remote_field.model is StaffActivity
            and model.objects.filter(pk=parent.pk).exists()
        ):
            raise ValidationError(
                "Activity already belongs to an incompatible specialization."
            )
