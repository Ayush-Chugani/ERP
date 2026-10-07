"""Serialized scheduling commands. Never call these through unrestricted admin writes."""
import hashlib
import json
import logging
import time
from datetime import timedelta
from functools import wraps
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError, ObjectDoesNotExist
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Max
from rest_framework.exceptions import ValidationError, NotFound
from apps.term_registration.models import ProgrammeTermOffering, CourseOfferingSection
from . import models as m
from .engine import (SchedulingConflict, scope, policy_for, validate_assignment,
    validate_session, operational, check_collisions, check_contact_workload)
from .policies import require_programme, require_institution, require_resources, grants


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def command(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        started = time.monotonic()
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='organization', model='university')
                kwargs['actor'] = get_user_model().objects.get(pk=kwargs['actor'].pk)
                return fn(*args, **kwargs)
        except ModelValidationError as exc:
            raise ValidationError(getattr(exc, 'message_dict', exc.messages)) from None
        except ObjectDoesNotExist:
            raise NotFound('Scheduling resource unavailable.') from None
        except IntegrityError as exc:
            if exc.args and exc.args[0] in (1062, 1451, 1452, 3819, 4025):
                raise SchedulingConflict('Duplicate or invalid scheduling references.') from None
            raise
        except OperationalError as exc:
            if exc.args and exc.args[0] in (1205, 1213):
                raise SchedulingConflict('Scheduling is busy. Retry the same idempotency key after a short delay.') from None
            raise
        finally:
            logging.getLogger(__name__).info('timetable_command', extra={
                'command': fn.__name__, 'duration_ms': round((time.monotonic() - started) * 1000),
                'actor_id': getattr(kwargs.get('actor'), 'pk', None)})
    return run


def save(obj):
    obj.full_clean()
    obj.save()
    return obj


def check_version(obj, expected):
    if expected is None or str(obj.version) != str(expected):
        raise SchedulingConflict('Stale version. Reload before retrying.')


def reason_required(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValidationError('Supply a nonblank reason of at most 500 characters.')


def snapshot(obj):
    # Explicitly exclude arbitrary personal data and solver inputs from audit payloads.
    fields = ['version', 'status', 'assignment_status', 'workload_hours', 'employee_id',
        'course_offering_section_id', 'faculty_assignment_id', 'room_id', 'time_slot_id',
        'start_date', 'end_date', 'effective_from', 'effective_to', 'day_of_week', 'number',
        'weekly_limit', 'require_competency', 'max_sessions', 'max_solver_jobs',
        'kind', 'date', 'start_time', 'end_time', 'sequence', 'cross_department_authorized']
    return {field: str(getattr(obj, field)) for field in fields if hasattr(obj, field)}


def evidence(obj, actor, institution_id, action, reason, before=None):
    reason_required(reason)
    correlation = str(uuid4())
    authority = {'superuser': actor.is_superuser, 'grants': list(grants(actor).filter(
        membership__institution_id=institution_id).values('id', 'membership_id', 'role', 'campus_id', 'department_id'))}
    m.TimetableAudit.objects.create(actor=actor, institution_id=institution_id, action=action,
        resource=obj._meta.model_name, record_id=obj.pk, before=before or {}, after=snapshot(obj),
        authority=authority, reason=reason.strip(), correlation_id=correlation)
    m.OutboxEvent.objects.create(institution_id=institution_id, topic=action,
        payload={'resource': obj._meta.model_name, 'id': obj.pk,
                 'version': getattr(obj, 'version', None), 'correlation_id': correlation})


def revision_for(actor, pk, action='manage_timetable'):
    # Scope before object lookup, including for command paths.
    from .policies import programmes
    return m.TimetableRevision.objects.select_for_update().filter(
        plan__programme_term_offering__programme__in=programmes(actor, action),
    ).get(pk=pk)


@command
def configure_policy(*, actor, institution_id, values, reason, expected_version=None):
    require_institution(actor, institution_id)
    allowed = {'weekly_limit', 'require_competency', 'max_sessions', 'max_solver_jobs'}
    if set(values) - allowed:
        raise ValidationError('Unsupported policy fields.')
    obj = m.SchedulingPolicy.objects.filter(institution_id=institution_id).first()
    before = snapshot(obj) if obj else {}
    if obj:
        check_version(obj, expected_version)
        obj.version += 1
    else:
        obj = m.SchedulingPolicy(institution_id=institution_id, created_by=actor)
    for field, value in values.items():
        setattr(obj, field, value)
    obj.updated_by = actor
    save(obj)
    evidence(obj, actor, institution_id, 'policy.configured', reason, before)
    return obj


@command
def create_assignment(*, actor, values, reason):
    allowed = {'course_offering_section_id', 'employee_id', 'assignment_role', 'workload_hours', 'start_date', 'end_date', 'cross_department_authorized'}
    if set(values) - allowed:
        raise ValidationError('Unsupported assignment fields.')
    section = CourseOfferingSection.objects.get(pk=values['course_offering_section_id'])
    require_programme(actor, section.programme_term_offering.programme_id)
    require_resources(actor, section, {'employees': values['employee_id']})
    if values.get('cross_department_authorized'):
        require_programme(actor, section.programme_term_offering.programme_id, 'cross_department_teaching')
    obj = m.FacultyAssignment(**values, created_by=actor, updated_by=actor)
    validate_assignment(obj)
    save(obj)
    evidence(obj, actor, scope(section).institution_id, 'assignment.created', reason)
    return obj


@command
def amend_assignment(*, actor, pk, expected_version, values, reason):
    obj = m.FacultyAssignment.objects.select_for_update().get(pk=pk)
    require_programme(actor, obj.course_offering_section.programme_term_offering.programme_id)
    require_resources(actor, obj.course_offering_section, {'employees': obj.employee_id})
    check_version(obj, expected_version)
    if obj.assignment_status != 'PLANNED':
        raise SchedulingConflict('Only planned assignments may be amended. Create a dated successor for active teaching.')
    if set(values) - {'workload_hours', 'start_date', 'end_date'}:
        raise ValidationError('Only planned workload and dates may be amended.')
    before = snapshot(obj)
    for field, value in values.items():
        setattr(obj, field, value)
    validate_assignment(obj)
    obj.version += 1
    obj.updated_by = actor
    save(obj)
    evidence(obj, actor, scope(obj.course_offering_section).institution_id, 'assignment.amended', reason, before)
    return obj


@command
def approve_workload_override(*, actor, values, reason):
    from apps.people_master.models import Employee
    employee = Employee.objects.get(pk=values['employee_id'])
    require_institution(actor, employee.institution_id, 'override_workload')
    if values['effective_from'].weekday() != 0 or values['effective_to'].weekday() != 6:
        raise ValidationError('Weekly overrides must start on Monday and end on Sunday.')
    if not 0 <= (values['effective_to'] - values['effective_from']).days <= 730:
        raise ValidationError('Override duration must be at most 731 days.')
    obj = save(m.WorkloadOverride(**values, actor=actor, reason=reason))
    evidence(obj, actor, employee.institution_id, 'workload.override_approved', reason)
    return obj


@command
def bulk_assignments(*, actor, rows, dry_run, reason):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
        raise ValidationError('Supply 1 to 50 allocations.')
    results = []
    conflicts = []
    with transaction.atomic():
        for index, values in enumerate(rows):
            try:
                obj = create_assignment(actor=actor, values=values, reason=reason)
                results.append({'row': index + 1, 'id': str(obj.pk) if not dry_run else None})
            except (ValidationError, SchedulingConflict) as exc:
                conflicts.append({'row': index + 1, 'conflict': exc.detail})
        if conflicts and not dry_run:
            raise ValidationError({'conflicts': conflicts})
        if dry_run:
            transaction.set_rollback(True)
    return {'dry_run': dry_run, 'results': results, 'conflicts': conflicts}


@command
def transition_assignment(*, actor, pk, expected_version, target, reason):
    obj = m.FacultyAssignment.objects.select_for_update().get(pk=pk)
    section = obj.course_offering_section
    require_programme(actor, section.programme_term_offering.programme_id)
    require_resources(actor, section, {'employees': obj.employee_id})
    check_version(obj, expected_version)
    transitions = {'PLANNED': {'ACTIVE', 'CANCELLED'}, 'ACTIVE': {'COMPLETED', 'CANCELLED'}}
    if target not in transitions.get(obj.assignment_status, set()):
        raise SchedulingConflict('Invalid assignment transition.')
    if target != 'ACTIVE' and m.TimetableSession.objects.filter(faculty_assignment=obj,
        revision__status__in=['APPROVED', 'PUBLISHED']).exists():
        raise SchedulingConflict('Withdraw or supersede dependent operational schedules first.')
    before = snapshot(obj)
    if target == 'ACTIVE':
        validate_assignment(obj, active=True)
    obj.assignment_status = target
    obj.version += 1
    obj.updated_by = actor
    save(obj)
    evidence(obj, actor, scope(section).institution_id, 'assignment.' + target.lower(), reason, before)
    return obj


@command
def create_revision(*, actor, offering_id, name, reason):
    offering = ProgrammeTermOffering.objects.get(pk=offering_id)
    require_programme(actor, offering.programme_id)
    if offering.status in ('COMPLETED', 'CANCELLED'):
        raise SchedulingConflict('Offering is closed.')
    plan, _ = m.TimetablePlan.objects.get_or_create(programme_term_offering=offering,
        defaults={'name': name, 'created_by': actor, 'updated_by': actor})
    number = (m.TimetableRevision.objects.filter(plan=plan).aggregate(n=Max('number'))['n'] or 0) + 1
    obj = save(m.TimetableRevision(plan=plan, number=number, created_by=actor, updated_by=actor))
    evidence(obj, actor, offering.programme.department.campus.institution_id, 'revision.created', reason)
    return obj


@command
def write_session(*, actor, revision_id, expected_version, values, reason, pk=None):
    revision = revision_for(actor, revision_id)
    check_version(revision, expected_version)
    if revision.status != 'DRAFT':
        raise SchedulingConflict('Only draft revisions can be edited.')
    allowed = {'course_offering_section_id', 'faculty_assignment_id', 'day_of_week', 'time_slot_id', 'room_id', 'effective_from', 'effective_to'}
    if set(values) - allowed:
        raise ValidationError('Unsupported session fields.')
    obj = m.TimetableSession.objects.get(pk=pk, revision=revision) if pk else m.TimetableSession(revision=revision, created_by=actor)
    before = snapshot(obj) if pk else {}
    for field, value in values.items():
        setattr(obj, field, value)
    obj.updated_by = actor
    if pk:
        obj.version += 1
    proposed = validate_session(obj)
    require_resources(actor, obj.course_offering_section, {'rooms': obj.room_id,
        'time-slots': obj.time_slot_id, 'employees': obj.faculty_assignment.employee_id if obj.faculty_assignment_id else None})
    policy = policy_for(obj.course_offering_section)
    sessions = m.TimetableSession.objects.filter(revision=revision).exclude(pk=pk)
    if sessions.count() >= policy.max_sessions:
        raise SchedulingConflict('Revision session limit reached.')
    existing = [item for session in sessions for item in validate_session(session)]
    check_collisions(proposed, existing + operational(exclude_plan=revision.plan_id,
        date_from=obj.effective_from, date_to=obj.effective_to))
    save(obj)
    revision.version += 1
    revision.updated_by = actor
    save(revision)
    evidence(obj, actor, scope(obj.course_offering_section).institution_id, 'session.saved', reason, before)
    return obj


@command
def remove_session(*, actor, revision_id, pk, expected_version, reason):
    revision = revision_for(actor, revision_id)
    check_version(revision, expected_version)
    if revision.status != 'DRAFT':
        raise SchedulingConflict('Only draft sessions can be removed.')
    obj = m.TimetableSession.objects.get(pk=pk, revision=revision)
    evidence(obj, actor, scope(obj.course_offering_section).institution_id, 'session.removed', reason, snapshot(obj))
    obj.delete()
    revision.version += 1
    revision.updated_by = actor
    save(revision)
    return revision


def publication_rows(revision):
    sessions = list(m.TimetableSession.objects.filter(revision=revision))
    if not sessions:
        raise SchedulingConflict('Cannot publish an empty revision.')
    rows = [item for session in sessions for item in validate_session(session, publication=True)]
    first, last = min(item.day for item in rows), max(item.day for item in rows)
    # Include the full boundary weeks for workload, even for a Monday-only revision.
    week_start = first - timedelta(days=first.weekday())
    week_end = last + timedelta(days=6 - last.weekday())
    existing = operational(exclude_plan=revision.plan_id,
        date_from=week_start, date_to=week_end)
    check_collisions(rows, existing)
    policy = policy_for(sessions[0].course_offering_section)
    own_employees = {item.employee_id for item in rows}
    check_contact_workload(rows + [item for item in existing if item.employee_id in own_employees], policy.weekly_limit)
    return rows


@command
def transition_revision(*, actor, pk, expected_version, target, reason):
    action = 'publish_timetable' if target in ('PUBLISHED', 'WITHDRAWN') else 'approve_timetable' if target == 'APPROVED' else 'manage_timetable'
    revision = revision_for(actor, pk, action)
    check_version(revision, expected_version)
    transitions = {'DRAFT': {'REVIEW'}, 'REVIEW': {'APPROVED', 'DRAFT'},
        'APPROVED': {'PUBLISHED', 'DRAFT'}, 'PUBLISHED': {'WITHDRAWN'},
        'WITHDRAWN': {'ARCHIVED'}, 'SUPERSEDED': {'ARCHIVED'}}
    if target not in transitions.get(revision.status, set()):
        raise SchedulingConflict('Invalid revision transition.')
    institution_id = revision.plan.programme_term_offering.programme.department.campus.institution_id
    before = snapshot(revision)
    if target in ('APPROVED', 'PUBLISHED'):
        for session in m.TimetableSession.objects.filter(revision=revision):
            require_resources(actor, session.course_offering_section, {'rooms': session.room_id,
                'time-slots': session.time_slot_id, 'employees': session.faculty_assignment.employee_id if session.faculty_assignment_id else None})
        rows = publication_rows(revision)
        if target == 'PUBLISHED':
            for old in m.TimetableRevision.objects.filter(plan=revision.plan, status='PUBLISHED'):
                previous = snapshot(old)
                old.status = 'SUPERSEDED'
                old.version += 1
                old.updated_by = actor
                save(old)
                evidence(old, actor, institution_id, 'timetable.superseded', reason, previous)
            for item in rows:
                m.PublishedOccurrence.objects.create(revision=revision, session_id=item.session_id,
                    course_offering_section_id=item.section_id, employee_id=item.employee_id,
                    class_section_id=item.class_section_id, class_batch_id=item.batch_id,
                    room_id=item.room_id, date=item.day, start_time=item.start, end_time=item.end,
                    student_ids=sorted(item.students))
    revision.status = target
    revision.version += 1
    revision.updated_by = actor
    save(revision)
    evidence(revision, actor, institution_id, 'timetable.' + target.lower(), reason, before)
    return revision


@command
def attest_availability(*, actor, values, reason):
    from apps.organization.models import Room
    from apps.people_master.models import Employee
    allowed = {'room_id', 'employee_id', 'effective_from', 'effective_to', 'day_of_week', 'start_time', 'end_time'}
    if set(values) - allowed or bool(values.get('room_id')) == bool(values.get('employee_id')):
        raise ValidationError('Select exactly one room or employee.')
    if values.get('room_id'):
        institution_id = Room.objects.get(pk=values['room_id']).building.campus.institution_id
    else:
        institution_id = Employee.objects.get(pk=values['employee_id']).institution_id
    require_institution(actor, institution_id, 'manage_timetable')
    obj = save(m.ResourceAvailability(**values, institution_id=institution_id,
        reason=reason, created_by=actor, updated_by=actor))
    evidence(obj, actor, institution_id, 'availability.attested', reason)
    return obj


@command
def add_exception(*, actor, occurrence_id, expected_sequence, values, reason):
    from copy import copy
    obj = m.PublishedOccurrence.objects.get(pk=occurrence_id)
    revision = revision_for(actor, obj.revision_id, 'change_occurrence')
    if revision.status != 'PUBLISHED':
        raise SchedulingConflict('Only operational occurrences accept exceptions.')
    sequence = m.OccurrenceException.objects.filter(occurrence=obj).aggregate(n=Max('sequence'))['n'] or 0
    if sequence != expected_sequence:
        raise SchedulingConflict('Stale occurrence sequence.')
    allowed = {'kind', 'date', 'start_time', 'end_time', 'room_id', 'faculty_assignment_id'}
    if set(values) - allowed:
        raise ValidationError('Unsupported exception fields.')
    change = m.OccurrenceException(occurrence=obj, sequence=sequence + 1,
        actor=actor, reason=reason, **values)
    change.full_clean()
    session = copy(obj.session)
    session.pk = obj.session_id
    session.room_id = change.room_id
    session.faculty_assignment_id = change.faculty_assignment_id
    # Use a detached slot to run the same eligibility/ownership validations.
    slot = copy(obj.session.time_slot)
    slot.start_time, slot.end_time = change.start_time, change.end_time
    session.time_slot = slot
    session.effective_from = session.effective_to = change.date
    session.day_of_week = change.date.isoweekday()
    require_resources(actor, session.course_offering_section, {'rooms': change.room_id,
        'employees': change.faculty_assignment.employee_id})
    if change.kind != 'CANCEL':
        require_resources(actor, session.course_offering_section, {'rooms': change.room_id,
            'employees': change.faculty_assignment.employee_id})
        proposed = validate_session(session, publication=True)
        from dataclasses import replace
        from .engine import current_membership
        proposed = [replace(item, class_section_id=obj.class_section_id,
            batch_id=obj.class_batch_id, students=current_membership(obj.course_offering_section_id, item.day, obj.student_ids)) for item in proposed]
        if change.room.capacity is not None and len(proposed[0].students) > change.room.capacity:
            raise SchedulingConflict('The published cohort exceeds replacement room capacity.')
        existing = [item for item in operational() if item.identity != obj.pk]
        check_collisions(proposed, existing)
        employee = proposed[0].employee_id
        check_contact_workload(proposed + [item for item in existing if item.employee_id == employee],
            policy_for(obj.course_offering_section).weekly_limit)
    elif change.room_id != obj.room_id or change.faculty_assignment_id != obj.session.faculty_assignment_id:
        raise ValidationError('Cancellation must retain the original resource references.')
    change.save()
    evidence(change, actor, scope(obj.course_offering_section).institution_id, 'occurrence.' + change.kind.lower(), reason)
    return change


@command
def idempotent(*, actor, key, operation, payload, execute):
    """Call only after API operation authorization, rechecked on every retry."""
    if not isinstance(key, str) or not 1 <= len(key) <= 100:
        raise ValidationError('Idempotency-Key must contain 1 to 100 characters.')
    fingerprint = digest({'operation': operation, 'payload': payload})
    receipt = m.CommandReceipt.objects.filter(actor=actor, key=key).first()
    if receipt:
        if receipt.digest != fingerprint:
            raise SchedulingConflict('Idempotency key was already used for different input.')
        return receipt.result
    result = execute(actor)
    m.CommandReceipt.objects.create(actor=actor, key=key, digest=fingerprint, result=result)
    return result
