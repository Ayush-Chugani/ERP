"""All calendar mutations pass through these atomic services."""
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Mapping
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, ValidationError, PermissionDenied, NotFound
from apps.organization.models import Campus
from .models import AcademicYear, AcademicTerm, Semester, TimeSlot, CalendarAudit
from .policies import scoped, can_create, campuses


class CalendarConflict(APIException):
    status_code = 409
    default_code = 'calendar_conflict'
    default_detail = 'The requested calendar change conflicts with existing data.'


class InvalidTransition(CalendarConflict):
    default_code = 'invalid_transition'
    default_detail = 'This lifecycle transition is not allowed.'


FIELDS = {
    AcademicYear: ('year_code', 'start_date', 'end_date'),
    AcademicTerm: ('academic_year_id', 'term_code', 'term_name', 'term_type', 'start_date', 'end_date', 'registration_start_date', 'registration_end_date'),
    Semester: ('semester_number', 'semester_name'),
    TimeSlot: ('campus_id', 'slot_code', 'start_time', 'end_time', 'is_break'),
}
PATHS = {AcademicYear: 'academic-years', AcademicTerm: 'academic-terms', Semester: 'semesters', TimeSlot: 'time-slots'}
TRANSITIONS = {
    AcademicYear: {'activate': ('ACTIVE', ('PLANNED',)), 'close': ('CLOSED', ('ACTIVE', 'PLANNED')), 'reopen': ('PLANNED', ('CLOSED',))},
    AcademicTerm: {'open_registration': ('REGISTRATION_OPEN', ('PLANNED',)), 'activate': ('ACTIVE', ('PLANNED', 'REGISTRATION_OPEN')), 'close': ('CLOSED', ('PLANNED', 'REGISTRATION_OPEN', 'ACTIVE')), 'reopen': ('PLANNED', ('CLOSED',))},
    TimeSlot: {'activate': (True, (False,)), 'deactivate': (False, (True,))},
}


@dataclass(frozen=True)
class WriteCommand:
    model: type
    actor: Any
    values: Mapping[str, Any] = field(default_factory=dict)
    record_id: int | None = None
    action: str = 'save'
    reason: str = ''
    correlation_id: str = ''


def snapshot(obj):
    names = (*FIELDS[type(obj)], obj._meta.pk.attname)
    if hasattr(obj, 'status'):
        names += ('status',)
    if isinstance(obj, TimeSlot):
        names += ('is_active',)
    result = {}
    for name in names:
        value = getattr(obj, name)
        if isinstance(value, (date, time)):
            value = value.isoformat()
        result[name] = value[:250] if isinstance(value, str) else value
    return result


def related_dependencies(obj):
    # Future integrations adding reverse FKs are conservatively protected.
    return any(rel.related_model.objects.filter(**{rel.field.name: obj}).exists()
               for rel in obj._meta.related_objects
               if rel.related_model is not AcademicTerm)


def validate_rules(obj, *, action, actor):
    if isinstance(obj, AcademicYear):
        if obj.status == 'ACTIVE' and AcademicYear.objects.exclude(pk=obj.pk).filter(status='ACTIVE').exists():
            raise CalendarConflict({'status': 'Only one shared academic year may be active.'})
        if obj.pk:
            for term in obj.terms.all():
                for name in ('start_date', 'end_date', 'registration_start_date', 'registration_end_date'):
                    value = getattr(term, name)
                    if value and not obj.start_date <= value <= obj.end_date:
                        raise CalendarConflict({'end_date': 'Year bounds would exclude existing term dates.'})
            if action == 'close' and obj.terms.exclude(status='CLOSED').exists():
                raise CalendarConflict('Close all terms before closing the year.')
    if isinstance(obj, AcademicTerm):
        year = obj.academic_year
        if year.status == 'CLOSED':
            raise CalendarConflict('The parent academic year is closed.')
        if obj.status in ('ACTIVE', 'REGISTRATION_OPEN') and year.status != 'ACTIVE':
            raise CalendarConflict('Activate the academic year first.')
    if isinstance(obj, TimeSlot) and obj.is_active and not obj.is_break:
        other = TimeSlot.objects.filter(campus_id=obj.campus_id, is_active=True, is_break=False,
            start_time__lt=obj.end_time, end_time__gt=obj.start_time).exclude(pk=obj.pk).order_by('pk').first()
        if other:
            if not scoped(TimeSlot, actor).filter(pk=other.pk).exists():
                raise CalendarConflict('An overlapping slot exists outside your visible record scope.')
            raise CalendarConflict({'conflicting_slot_id': other.pk, 'slot_code': other.slot_code,
                                    'start_time': other.start_time.isoformat(), 'end_time': other.end_time.isoformat()})


def execute(command: WriteCommand):
    model, values = command.model, dict(command.values)
    if model not in FIELDS:
        raise ValidationError('Unknown calendar resource.')
    if set(values) - set(FIELDS[model]):
        raise ValidationError('Unknown or protected fields.')
    if command.action != 'save' and values:
        raise ValidationError('Lifecycle actions accept only a reason.')
    if not isinstance(command.reason, str) or len(command.reason) > 250:
        raise ValidationError({'reason': 'Use at most 250 characters.'})
    if not isinstance(command.correlation_id, str) or len(command.correlation_id) > 64:
        raise ValidationError('Invalid correlation ID.')
    try:
        with transaction.atomic():
            # Same lock as organization/admin writers: ancestor status cannot race.
            ContentType.objects.select_for_update().get(app_label='organization', model='university')
            actor = get_user_model().objects.get(pk=command.actor.pk)
            permission = ('change' if command.record_id else 'add') if command.action == 'save' else command.action
            if command.record_id:
                obj = scoped(model, actor, action=permission).select_for_update().filter(pk=command.record_id).first()
                if obj is None:
                    raise NotFound()
            else:
                if command.action != 'save' or not can_create(actor, model):
                    raise PermissionDenied()
                obj = model()
            before = snapshot(obj) if command.record_id else {}
            if command.action == 'save':
                if getattr(obj, 'status', None) == 'CLOSED':
                    raise CalendarConflict('Reopen a closed period before editing.')
                if command.record_id and related_dependencies(obj):
                    raise CalendarConflict('Dependent records prevent editing this calendar record.')
                for name, value in values.items():
                    if name.endswith('_id') and (type(value) is not int or value < 1):
                        raise ValidationError({name: 'Use a positive integer ID.'})
                    if name == 'is_break' and type(value) is not bool:
                        raise ValidationError({name: 'Use a boolean.'})
                    if command.record_id and name in ('academic_year_id', 'campus_id') and value != getattr(obj, name):
                        raise CalendarConflict('Calendar ownership cannot be changed.')
                    setattr(obj, name, value)
            else:
                rule = TRANSITIONS.get(model, {}).get(command.action)
                if rule is None:
                    raise InvalidTransition()
                target, sources = rule
                attr = 'is_active' if model is TimeSlot else 'status'
                current = getattr(obj, attr)
                if command.action in ('close', 'reopen') and not command.reason.strip():
                    raise ValidationError({'reason': 'A reason is required.'})
                if current == target:
                    return obj  # No-op retry: no duplicate audit event.
                if current not in sources:
                    raise InvalidTransition()
                if related_dependencies(obj):
                    raise CalendarConflict('Dependent records require an integration review before this transition.')
                setattr(obj, attr, target)
            if model is TimeSlot:
                parent = campuses(actor, write=True).select_for_update().filter(pk=obj.campus_id).first()
                if parent is None:
                    raise ValidationError({'campus_id': 'Select a campus in your management scope.'})
                obj.campus = parent
                if (not command.record_id or command.action == 'activate') and not (parent.is_active and parent.institution.is_active and parent.institution.university.is_active):
                    raise CalendarConflict('New assignments require active campus ancestors.')
            if model is AcademicTerm:
                parent = AcademicYear.objects.select_for_update().filter(pk=obj.academic_year_id).first()
                if parent is None:
                    raise ValidationError({'academic_year_id': 'Select an existing academic year.'})
                obj.academic_year = parent
            obj.full_clean()
            validate_rules(obj, action=command.action, actor=actor)
            obj.save()
            if model is TimeSlot and not scoped(model, actor, action=permission).filter(pk=obj.pk).exists():
                raise PermissionDenied('Record limits do not permit this record.')
            after = snapshot(obj)
            if before != after:
                CalendarAudit.objects.create(actor=actor, institution_id=obj.campus.institution_id if model is TimeSlot else None,
                    resource=PATHS[model], record_id=obj.pk, action=command.action if command.action != 'save' else ('update' if before else 'create'),
                    before=before, after=after, reason=command.reason.strip(), correlation_id=command.correlation_id or str(uuid4()))
            return obj
    except IntegrityError as error:
        if error.args and error.args[0] in (1062, 1451, 1452, 3819, 4025):
            raise CalendarConflict('Duplicate values, invalid constraints or protected references.') from None
        raise
    except ModelValidationError as error:
        if any(e.code in ('unique', 'unique_together') for group in getattr(error, 'error_dict', {}).values() for e in group):
            raise CalendarConflict('A calendar record with these values already exists.') from None
        raise ValidationError(getattr(error, 'message_dict', {'non_field_errors': error.messages})) from None


def save_record(model, values, *, actor, pk=None, correlation_id=''):
    return execute(WriteCommand(model, actor, values, pk, correlation_id=correlation_id))


def transition(model, pk, action, *, actor, reason='', correlation_id=''):
    return execute(WriteCommand(model, actor, record_id=pk, action=action, reason=reason, correlation_id=correlation_id))
