from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from apps.core.models import AppendOnlyQuerySet


def scope_shape():
    branches = Q()
    for scope in ('GLOBAL', 'INSTITUTION', 'CAMPUS', 'DEPARTMENT', 'PROGRAMME', 'SELF'):
        branches |= Q(scope_type=scope, **{
            f'{name}__isnull': scope != name.upper()
            for name in ('institution', 'campus', 'department', 'programme')})
    return branches


class Evidence(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Security evidence is append-only.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Security evidence is append-only.')


class LinkProjection(Evidence):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        raise ValidationError('Use the People invitation/link owner service.')
