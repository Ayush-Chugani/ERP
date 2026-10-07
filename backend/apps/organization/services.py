from django.db import transaction, IntegrityError
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from apps.common_reference.services import Conflict, ReferenceConflict
from apps.common_reference.selectors import is_available as state_available
from .models import OrganizationAudit
from .catalogue import BY_MODEL, writable
from .selectors import scoped, available


def snapshot(obj):
    if obj is None: return {}
    return {f.attname:(getattr(obj,f.attname)[:500] if isinstance(getattr(obj,f.attname),str) else getattr(obj,f.attname)) for f in writable(type(obj))}


def impact(obj,actor=None):
    counts={}
    for relation in obj._meta.related_objects:
        query=relation.related_model.objects.filter(**{relation.field.name:obj})
        counts[relation.related_model._meta.label_lower]=query.count()
    move_allowed=not any(counts.values())
    if actor is not None:
        counts={relation.related_model._meta.label_lower:scoped(relation.related_model,actor).filter(**{relation.field.name:obj}).count()
                for relation in obj._meta.related_objects if relation.related_model in BY_MODEL}
    return {'references':counts,'move_allowed':move_allowed,'deactivation_cascades':False}


def validate(obj):
    obj.clean()
    obj.full_clean()


def save_record(model,values,*,actor,pk=None,move=False):
    actor=get_user_model().objects.get(pk=actor.pk)
    r=BY_MODEL[model]
    allowed={f.name for f in writable(model)}
    if set(values)-allowed: raise ValidationError('Unknown or read-only fields.')
    if 'is_active' in values and type(values['is_active']) is not bool: raise ValidationError({'is_active':'Use a boolean.'})
    try:
        with transaction.atomic():
            ContentType.objects.select_for_update().get(app_label='organization',model='university')
            if pk:
                obj=scoped(model,actor,write=True).select_for_update().filter(pk=pk).first()
                if obj is None: raise NotFound()
            else:
                obj=model()
                if not actor.is_active: raise PermissionDenied()
                if not actor.is_superuser and not r.parent: raise PermissionDenied()
            before=snapshot(obj) if pk else {}
            if r.parent:
                parent=values.get(r.parent,getattr(obj,r.parent,None) if pk else None)
                if parent is None: raise ValidationError({r.parent+'_id':'Parent is required.'})
                changed=not pk or getattr(obj,r.parent+'_id')!=parent.pk
                if changed:
                    if not scoped(type(parent),actor,write=True).filter(pk=parent.pk).exists(): raise PermissionDenied('Parent is outside your management scope.')
                    parent=type(parent).objects.select_for_update().get(pk=parent.pk)
                    if not available(parent): raise ValidationError({r.parent+'_id':'New assignments require active ancestors.'})
                    if pk:
                        if not move: raise ReferenceConflict('Use the reviewed move action to change ownership.')
                        if not impact(obj)['move_allowed']: raise ReferenceConflict('Historical references prevent this move.')
                        old_parent=getattr(obj,r.parent)
                        def tenant(record):
                            descriptor=BY_MODEL[type(record)]
                            if descriptor.institution=='pk': return record.pk
                            if descriptor.institution:
                                for part in descriptor.institution.split('__'): record=getattr(record,part)
                                return record.pk
                            return None
                        if tenant(old_parent)!=tenant(parent): raise ReferenceConflict('Cross-institution moves are not allowed.')
                    values[r.parent]=parent
            if 'state' in values and values['state'] is not None and (not pk or obj.state_id!=values['state'].pk):
                state=type(values['state']).objects.select_for_update().get(pk=values['state'].pk)
                if not actor.has_perm('common_reference.view_state') or not state_available(state): raise ValidationError({'state_id':'Select an authorized active state.'})
                values['state']=state
            for name,value in values.items(): setattr(obj,name,value)
            validate(obj)
            obj.save()
            if (not pk or move) and not scoped(model,actor,write=True).filter(pk=obj.pk).exists(): raise PermissionDenied('Record is outside your management scope.')
            after=snapshot(obj)
            if before!=after:
                action='create' if not pk else 'move' if move else 'update'
                if before and before['is_active']!=after['is_active']: action='reactivate' if after['is_active'] else 'deactivate'
                OrganizationAudit.objects.create(actor=actor,resource=r.path,record_id=obj.pk,action=action,before=before,after=after)
            return obj
    except IntegrityError as error:
        if error.args and error.args[0]==1062: raise Conflict()
        if error.args and error.args[0] in (1451,1452): raise ReferenceConflict()
        raise
    except DjangoValidationError as error:
        entries=getattr(error,'error_dict',{})
        if any(e.code in ('unique','unique_together') for group in entries.values() for e in group): raise Conflict()
        raise ValidationError(getattr(error,'message_dict',{'non_field_errors':error.messages}))
