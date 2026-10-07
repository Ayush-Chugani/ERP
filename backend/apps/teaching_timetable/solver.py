"""Bounded deterministic backtracking adapter; no model writes during search."""
import random
from decimal import Decimal
import time
from dataclasses import asdict
from datetime import date, time as clock_time
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m
from .engine import Occurrence, validate_session, operational, conflicts, policy_for, SchedulingConflict
from .services import command, revision_for, check_version, digest, save, evidence, write_session


def encode(item):
    value = asdict(item)
    value['day'] = str(item.day)
    value['start'] = str(item.start)
    value['end'] = str(item.end)
    value['students'] = sorted(item.students)
    return value


def decode(value):
    return Occurrence(**{**value, 'day': date.fromisoformat(value['day']),
        'start': clock_time.fromisoformat(value['start']), 'end': clock_time.fromisoformat(value['end']),
        'students': frozenset(value['students'])})


def build_snapshot(revision, choices):
    """Materialize eligibility and occupancy; later acceptance reconstructs it."""
    if not isinstance(choices, list) or not 1 <= len(choices) <= 100:
        raise ValidationError('Supply 1 to 100 session requests.')
    if any(not isinstance(options, list) for options in choices) or sum(map(len, choices)) > 100:
        raise ValidationError('A job is limited to 100 alternatives in total.')
    tasks = []
    for alternatives in choices:
        if not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 20:
            raise ValidationError('Each session requires 1 to 20 alternatives.')
        options = []
        for values in alternatives:
            allowed = {'course_offering_section_id', 'faculty_assignment_id', 'room_id', 'time_slot_id', 'day_of_week', 'effective_from', 'effective_to'}
            if set(values) != allowed:
                raise ValidationError('Each alternative must specify all session fields.')
            parsed = {**values, 'effective_from': date.fromisoformat(str(values['effective_from'])),
                'effective_to': date.fromisoformat(str(values['effective_to']))}
            session = m.TimetableSession(revision=revision, **parsed)
            rows = validate_session(session, publication=True)
            options.append({'values': {k: str(v) if isinstance(v, date) else v for k, v in parsed.items()},
                'occurrences': [encode(item) for item in rows]})
        tasks.append(options)
    existing = operational(exclude_plan=revision.plan_id)
    for session in m.TimetableSession.objects.filter(revision=revision):
        existing.extend(validate_session(session, publication=True))
    section = m.TimetableSession(revision=revision, **{**choices[0][0],
        'effective_from': date.fromisoformat(str(choices[0][0]['effective_from'])),
        'effective_to': date.fromisoformat(str(choices[0][0]['effective_to']))}).course_offering_section
    policy = policy_for(section)
    employees = {row['employee_id'] for task in tasks for option in task for row in option['occurrences']}
    overrides = list(m.WorkloadOverride.objects.filter(employee_id__in=employees).order_by('-pk').values(
        'employee_id', 'effective_from', 'effective_to', 'weekly_limit'))
    import json
    return {'revision_version': revision.version, 'tasks': tasks,
        'weekly_limit': str(policy.weekly_limit), 'policy_version': policy.version,
        'employees': sorted(employees), 'overrides': json.loads(json.dumps(overrides, default=str)),
        'existing': sorted((encode(item) for item in existing), key=lambda v: (v['day'], v['session_id'], v['start'])),
        'choices': choices}


def solve(snapshot, seed=0, *, max_nodes=20000, timeout=10.0, cancelled=lambda: False):
    rng = random.Random(seed)
    tasks = []
    for options in snapshot['tasks']:
        order = list(range(len(options)))
        rng.shuffle(order)
        tasks.append(order)
    existing = [decode(item) for item in snapshot['existing']]
    started = time.monotonic()
    nodes = 0
    aborted = False
    candidates = []

    def workload_ok(rows):
        totals = {}
        for row in rows:
            if row.employee_id not in snapshot.get('employees', []):
                continue
            key = (row.employee_id, row.day.isocalendar()[:2])
            seconds = row.end.hour*3600+row.end.minute*60+row.end.second-row.start.hour*3600-row.start.minute*60-row.start.second
            totals[key] = totals.get(key, 0) + seconds
            cap = next((value['weekly_limit'] for value in snapshot.get('overrides', [])
                if value['employee_id'] == row.employee_id and value['effective_from'] <= str(row.day) <= value['effective_to']), snapshot.get('weekly_limit', '9999'))
            if Decimal(totals[key]) / 3600 > Decimal(cap):
                return False
        return True

    def score(rows):
        # Soft objective: reduce idle minutes between faculty/class meetings.
        groups = {}
        for row in rows:
            for resource in [('faculty', row.employee_id), ('class', row.class_section_id)]:
                if resource[1] is not None:
                    groups.setdefault((resource, row.day), []).append(row)
        total = 0
        for meetings in groups.values():
            ordered = sorted(meetings, key=lambda row: row.start)
            for left, right in zip(ordered, ordered[1:]):
                total += max(0, right.start.hour * 60 + right.start.minute - left.end.hour * 60 - left.end.minute)
        return total

    def search(index, occupied, selected):
        nonlocal nodes, aborted
        if nodes >= max_nodes or time.monotonic() - started >= timeout or cancelled():
            aborted = True
            return None
        if index == len(tasks):
            candidates.append({'selected': selected, 'score': score(occupied)})
            candidates.sort(key=lambda item: (item['score'], item['selected']))
            del candidates[3:]
            return None
        for option in tasks[index]:
            nodes += 1
            rows = [decode(item) for item in snapshot['tasks'][index][option]['occurrences']]
            if any(conflicts(left, right) for left in rows for right in occupied):
                continue
            if not workload_ok(occupied + rows):
                continue
            search(index + 1, occupied + rows, selected + [option])
            if aborted:
                return None
        return None

    search(0, existing, [])
    result = candidates[0]['selected'] if candidates else None
    return {'selected': result, 'candidates': candidates, 'nodes': nodes,
        'complete_search': not aborted,
        'outcome': 'FEASIBLE' if result is not None else 'LIMIT_REACHED' if aborted else 'INFEASIBLE',
        'explanation': 'Candidates ranked by faculty/class idle minutes (lower is better). Bounded search does not guarantee a global optimum; acceptance revalidates workload and all current inputs.'}


@command
def queue_job(*, actor, revision_id, expected_version, choices, seed, reason):
    revision = revision_for(actor, revision_id)
    check_version(revision, expected_version)
    if revision.status != 'DRAFT':
        raise SchedulingConflict('Generation requires a draft revision.')
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValidationError('Seed must be an integer between 0 and 2147483647.')
    if not isinstance(choices, list) or not choices or any(not isinstance(group, list) or not group for group in choices) or sum(map(len, choices)) > 100:
        raise ValidationError('Supply between 1 and 100 alternatives in nonempty session groups.')
    from apps.term_registration.models import CourseOfferingSection
    from .policies import require_programme, require_resources
    for group in choices:
        for values in group:
            section = CourseOfferingSection.objects.get(pk=values['course_offering_section_id'])
            require_programme(actor, section.programme_term_offering.programme_id)
            assignment = m.FacultyAssignment.objects.get(pk=values['faculty_assignment_id'])
            require_resources(actor, section, {'employees': assignment.employee_id,
                'rooms': values['room_id'], 'time-slots': values['time_slot_id']})
    snapshot = build_snapshot(revision, choices)
    section_id = choices[0][0]['course_offering_section_id']
    from apps.term_registration.models import CourseOfferingSection
    policy = policy_for(CourseOfferingSection.objects.get(pk=section_id))
    institution_id = policy.institution_id
    pending = m.SolverJob.objects.filter(status__in=['QUEUED', 'RUNNING'],
        revision__plan__programme_term_offering__programme__department__campus__institution_id=institution_id)
    if pending.count() >= policy.max_solver_jobs:
        raise SchedulingConflict('Institution solver quota reached.')
    obj = save(m.SolverJob(revision=revision, seed=seed, input_snapshot=snapshot,
        input_digest=digest(snapshot), result={'outcome': 'QUEUED'}, created_by=actor, updated_by=actor))
    evidence(obj, actor, institution_id, 'solver.queued', reason)
    return obj


@command
def cancel_job(*, actor, pk, expected_version, reason):
    obj = m.SolverJob.objects.get(pk=pk)
    revision_for(actor, obj.revision_id)
    check_version(obj, expected_version)
    if obj.status not in ('QUEUED', 'RUNNING', 'SUCCEEDED'):
        raise SchedulingConflict('Job cannot be cancelled in its current state.')
    obj.status = 'CANCELLED'
    obj.version += 1
    obj.updated_by = actor
    save(obj)
    evidence(obj, actor, obj.revision.plan.programme_term_offering.programme.department.campus.institution_id,
        'solver.cancelled', reason)
    return obj


@command
def accept_job(*, actor, pk, expected_version, reason, candidate_index=0):
    obj = m.SolverJob.objects.get(pk=pk)
    revision = revision_for(actor, obj.revision_id)
    check_version(obj, expected_version)
    if obj.status != 'SUCCEEDED' or obj.result.get('selected') is None or revision.status != 'DRAFT':
        raise SchedulingConflict('No candidate is available for acceptance.')
    current = build_snapshot(revision, obj.input_snapshot['choices'])
    if digest(current) != obj.input_digest:
        raise SchedulingConflict('Solver inputs changed. Generate a new candidate.')
    candidates = obj.result.get('candidates', [{'selected': obj.result['selected']}])
    if type(candidate_index) is not int or not 0 <= candidate_index < len(candidates):
        raise ValidationError('Select a candidate returned by this job.')
    for index, option in enumerate(candidates[candidate_index]['selected']):
        values = current['tasks'][index][option]['values']
        parsed = {**values, 'effective_from': date.fromisoformat(values['effective_from']),
            'effective_to': date.fromisoformat(values['effective_to'])}
        write_session(actor=actor, revision_id=revision.pk, expected_version=revision.version,
            values=parsed, reason=reason)
        revision.refresh_from_db()
    # Candidate acceptance also checks publication prerequisites and total workload.
    from .services import publication_rows
    publication_rows(revision)
    obj.status = 'ACCEPTED'
    obj.version += 1
    obj.updated_by = actor
    save(obj)
    evidence(obj, actor, revision.plan.programme_term_offering.programme.department.campus.institution_id,
        'solver.accepted', reason)
    return obj


def run_next():
    """Management-command worker. Claim briefly, compute without row locks."""
    from django.db import transaction
    with transaction.atomic():
        obj = m.SolverJob.objects.select_for_update(skip_locked=True).filter(status='QUEUED').order_by('pk').first()
        if obj is None:
            return False
        obj.status = 'RUNNING'
        obj.started_at = timezone.now()
        obj.version += 1
        obj.save()
        pk, snapshot, seed = obj.pk, obj.input_snapshot, obj.seed
    try:
        result = solve(snapshot, seed, cancelled=lambda: not m.SolverJob.objects.filter(pk=pk, status='RUNNING').exists())
        status = 'SUCCEEDED' if result['selected'] is not None else 'FAILED'
    except Exception:
        import logging
        logging.getLogger(__name__).exception('M8 solver failed', extra={'job_id': pk})
        result, status = {'outcome': 'FAILED', 'explanation': 'Worker failed; inspect server logs.'}, 'FAILED'
    with transaction.atomic():
        obj = m.SolverJob.objects.select_for_update().get(pk=pk)
        if obj.status == 'RUNNING':
            obj.status, obj.result = status, result
            obj.finished_at = timezone.now()
            obj.version += 1
            obj.save()
    return True
