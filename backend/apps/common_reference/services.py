from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import APIException, ValidationError, NotFound, PermissionDenied
from apps.core.models import ReferenceAuditEvent
from .resources import RESOURCES
from .selectors import is_available


class Conflict(APIException):
    status_code = 409
    default_code = 'duplicate_reference'
    default_detail = 'A reference with these values already exists.'


class ReferenceConflict(Conflict):
    default_code = 'protected_reference'
    default_detail = 'The reference is in use or its parent is unavailable.'


def snapshot(obj):
    # Explicit catalogue allowlist only. Each field is already bounded by its
    # model; cap strings defensively and never serialize arbitrary relations.
    writable = next(row[2] for row in RESOURCES if row[0] is type(obj))
    result = {obj._meta.pk.name: obj.pk}
    for name in writable:
        value = getattr(obj, name)
        result[name] = value[:500] if isinstance(value, str) else value
    return result


def write_reference(model, values, pk=None, *, actor, source='api'):
    operation = 'add' if pk is None else 'change'
    if not (actor and actor.is_authenticated and actor.is_active and
            actor.has_perm('common_reference.maintain_reference') and
            actor.has_perm(f'common_reference.{operation}_{model._meta.model_name}')):
        raise PermissionDenied('Global maintenance and model write permissions are required.')
    if source not in ('api', 'admin', 'seed'):
        raise ValueError('Unsupported audit source.')
    writable = next(row[2] for row in RESOURCES if row[0] is model)
    allowed = {model._meta.get_field(name).name for name in writable}
    if set(values) - allowed:
        raise ValidationError('Unsupported writable fields.')
    for name in ('is_active', 'requires_verification'):
        if name in values and type(values[name]) is not bool:
            raise ValidationError({name: ['Use a boolean.']})
    try:
        with transaction.atomic():
            ContentType.objects.select_for_update().get(app_label='common_reference', model='country')
            try:
                obj = model.objects.select_for_update().get(pk=pk) if pk is not None else model()
            except model.DoesNotExist:
                raise NotFound()
            before = snapshot(obj) if pk is not None else {}
            for field in model._meta.fields:
                if not field.is_relation or field.name not in values:
                    continue
                parent = values[field.name]
                if parent is not None:
                    try:
                        parent = field.related_model.objects.get(pk=parent.pk)
                    except field.related_model.DoesNotExist:
                        raise ReferenceConflict()
                    values[field.name] = parent
                changed = pk is None or getattr(obj, field.attname) != getattr(parent, 'pk', None)
                if changed and parent is not None and not is_available(parent):
                    raise ValidationError({field.attname: ['New assignments require an active parent and active ancestors.']})
            for key, value in values.items():
                setattr(obj, key, value)
            obj.save()
            after = snapshot(obj)
            if before != after:
                action = 'create' if pk is None else 'update'
                if before and before['is_active'] != after['is_active']:
                    action = 'reactivate' if after['is_active'] else 'deactivate'
                ReferenceAuditEvent.objects.create(actor=actor, action=action,
                    resource=model._meta.db_table, record_id=obj.pk, source=source,
                    before=before, after=after)
            return obj
    except ProtectedError:
        raise ReferenceConflict()
    except IntegrityError as exc:
        # The write AND audit savepoint have rolled back before translation.
        number = exc.args[0] if exc.args else None
        if number == 1062:
            raise Conflict()
        if number in (1451, 1452):
            raise ReferenceConflict()
        raise
    except ModelValidationError as exc:
        errors = getattr(exc, 'error_dict', {})
        if any(getattr(error, 'code', None) in ('unique', 'unique_together') for group in errors.values() for error in group):
            raise Conflict()
        raise ValidationError(getattr(exc, 'message_dict', {'non_field_errors': exc.messages}))
