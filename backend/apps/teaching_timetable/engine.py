"""Validation and collision queries shared by manual planning and publication."""
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from django.db.models import Q
from rest_framework.exceptions import APIException, ValidationError
from apps.people_master.models import EmployeeAssignment, EmployeeCompetency
from apps.term_registration.models import CourseOfferingSectionStudent
from . import models as m
from .intervals import Meeting, occurrence_dates, assignment_covers_occurrences


class SchedulingConflict(APIException):
    status_code = 409
    default_code = 'scheduling_conflict'
    default_detail = 'Scheduling conflicts with current data.'


def scope(section):
    return section.programme_term_offering.programme.department.campus


def policy_for(section):
    try:
        return m.SchedulingPolicy.objects.get(institution_id=scope(section).institution_id)
    except m.SchedulingPolicy.DoesNotExist:
        raise SchedulingConflict('Configure the institution weekly workload policy first.') from None


def validate_assignment(obj, *, active=False):
    section = obj.course_offering_section
    offering = section.programme_term_offering
    campus = scope(section)
    term = offering.academic_term
    end = obj.end_date or term.end_date
    if not term.start_date <= obj.start_date <= end <= term.end_date:
        raise ValidationError('Assignment dates must fall inside the academic term.')
    if obj.employee.institution_id != campus.institution_id or obj.employee.employment_status != 'ACTIVE':
        raise ValidationError('Employee must be active in the offering institution.')
    if offering.status in ('COMPLETED', 'CANCELLED') or section.course_offering.status in ('COMPLETED', 'CANCELLED') or not section.class_section.is_active or (section.class_batch_id and not section.class_batch.is_active):
        raise SchedulingConflict('The offering, class section or batch is unavailable.')
    employment = EmployeeAssignment.objects.filter(employee=obj.employee, campus=campus,
        start_date__lte=obj.start_date).filter(Q(end_date__isnull=True) | Q(end_date__gte=end))
    if not obj.cross_department_authorized:
        employment = employment.filter(department_id=offering.programme.department_id)
    if not employment.exists():
        raise SchedulingConflict('A dated employment assignment in the teaching department is required.')
    policy = policy_for(section)
    if policy.require_competency and not EmployeeCompetency.objects.filter(
        employee=obj.employee, course=section.course_offering.course,
        competency_level__in=['INTERMEDIATE', 'ADVANCED', 'EXPERT'],
    ).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=obj.start_date)).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=end),
    ).exists():
        raise SchedulingConflict('Current course competency evidence is required.')
    overlap = m.FacultyAssignment.objects.filter(
        assignment_status__in=['PLANNED', 'ACTIVE'], start_date__lte=end,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=obj.start_date)).exclude(pk=obj.pk)
    same = overlap.filter(course_offering_section=section, assignment_role=obj.assignment_role)
    if same.filter(employee=obj.employee).exists() or (obj.assignment_role == 'PRIMARY_INSTRUCTOR' and same.exists()):
        raise SchedulingConflict('An incompatible assignment role overlaps these dates.')
    if active and obj.workload_hours is None:
        raise ValidationError('Set planned weekly workload before activation.')
    # Sweep assignment boundaries, avoiding overcounting disjoint episodes.
    rows = list(overlap.filter(employee=obj.employee)) + [obj]
    boundaries = {row.start_date for row in rows} | {obj.start_date}
    for day in boundaries:
        if not obj.start_date <= day <= end:
            continue
        total = sum((row.workload_hours or Decimal(0)) for row in rows
                    if row.start_date <= day <= (row.end_date or row.course_offering_section.programme_term_offering.academic_term.end_date))
        if total > weekly_limit(obj.employee_id, day, policy.weekly_limit):
            raise SchedulingConflict('Planned weekly workload exceeds the configured limit.')


def weekly_limit(employee_id, day, default):
    override = m.WorkloadOverride.objects.filter(employee_id=employee_id,
        effective_from__lte=day, effective_to__gte=day).order_by('-pk').first()
    return override.weekly_limit if override else default


def meeting_for(session):
    section = session.course_offering_section
    return Meeting(session.day_of_week, session.time_slot.start_time, session.time_slot.end_time,
        session.effective_from, session.effective_to, session.room_id,
        session.faculty_assignment.employee_id if session.faculty_assignment_id else None,
        section.class_section_id, section.class_batch_id)


def roster(section, day):
    return frozenset(CourseOfferingSectionStudent.objects.filter(
        course_offering_section=section, effective_from__lte=day,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=day)).values_list(
        'course_registration__term_registration__enrolment__student_id', flat=True,
    ))


@dataclass(frozen=True)
class Occurrence:
    identity: int | None
    session_id: int
    section_id: int
    class_section_id: int
    batch_id: int | None
    employee_id: int | None
    room_id: int | None
    day: date
    start: object
    end: object
    students: frozenset[int]


def validate_session(session, *, publication=False):
    section = session.course_offering_section
    campus = scope(section)
    offering = section.programme_term_offering
    if session.revision.plan.programme_term_offering_id != offering.pk:
        raise ValidationError('Session and revision must belong to the same programme-term offering.')
    term = offering.academic_term
    if publication and term.status not in ('REGISTRATION_OPEN', 'ACTIVE'):
        raise SchedulingConflict('Publication requires an open or active academic term.')
    if not term.start_date <= session.effective_from <= session.effective_to <= term.end_date:
        raise ValidationError('Session dates must fall inside the academic term.')
    if (session.effective_to - session.effective_from).days > 730:
        raise ValidationError('A scheduling period cannot exceed 731 days.')
    if not session.time_slot.is_active or session.time_slot.is_break or session.time_slot.campus_id != campus.pk:
        raise ValidationError('Select an active teaching time slot in the offering campus.')
    if session.room_id:
        room = session.room
        if room.building.campus_id != campus.pk or not room.is_active or not room.building.is_active:
            raise ValidationError('Select an active room in the offering campus.')
        required = (section.class_batch.capacity if section.class_batch_id else section.class_section.capacity)
        if room.capacity is None or required is None or room.capacity < required:
            raise SchedulingConflict('Verified room and cohort capacity is required, with sufficient seats.')
        if section.session_type == 'PRACTICAL' and room.room_type != 'LAB':
            raise SchedulingConflict('Practical sessions require a laboratory room.')
    meeting = meeting_for(session)
    dates = occurrence_dates(meeting)
    if not dates:
        raise ValidationError('The recurrence contains no teaching date.')
    if session.faculty_assignment_id:
        assignment = session.faculty_assignment
        if assignment.course_offering_section_id != section.pk:
            raise ValidationError('Faculty assignment belongs to a different course section.')
        validate_assignment(assignment, active=publication)
        if not assignment_covers_occurrences(meeting, assignment.start_date, assignment.end_date):
            raise SchedulingConflict('Assignment must cover every teaching occurrence.')
        if publication and assignment.assignment_status != 'ACTIVE':
            raise SchedulingConflict('Publication requires an active faculty assignment.')
    if publication and (not session.room_id or not session.faculty_assignment_id):
        raise SchedulingConflict('Publication requires both a room and an instructor.')
    roster_rows = list(CourseOfferingSectionStudent.objects.filter(course_offering_section=section,
        effective_from__lte=session.effective_to).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gt=session.effective_from)).values_list(
        'course_registration__term_registration__enrolment__student_id', 'effective_from', 'effective_to'))
    availability = list(m.ResourceAvailability.objects.filter(institution_id=campus.institution_id,
        day_of_week=session.day_of_week, effective_from__lte=session.effective_to,
        effective_to__gte=session.effective_from).filter(
        Q(employee_id=meeting.employee_id) | Q(room_id=meeting.room_id))) if publication else []
    rows = []
    for day in dates:
        students = frozenset(pk for pk, start, end in roster_rows if start <= day and (end is None or day < end))
        if session.room_id and len(students) > session.room.capacity:
            raise SchedulingConflict('The current roster exceeds room capacity.')
        item = Occurrence(None, session.pk or 0, section.pk, section.class_section_id,
            section.class_batch_id, meeting.employee_id, meeting.room_id, day,
            meeting.start, meeting.end, students)
        if publication:
            require_availability(item, campus.institution_id, availability)
        rows.append(item)
    return rows


def require_availability(item, institution_id, evidence=None):
    if evidence is None:
        evidence = list(m.ResourceAvailability.objects.filter(institution_id=institution_id,
            day_of_week=item.day.isoweekday(), effective_from__lte=item.day, effective_to__gte=item.day))
    for field, pk in [('employee_id', item.employee_id), ('room_id', item.room_id)]:
        if pk is None or not any(getattr(row, field) == pk and row.day_of_week == item.day.isoweekday()
            and row.effective_from <= item.day <= row.effective_to
            and row.start_time <= item.start and row.end_time >= item.end for row in evidence):
            raise SchedulingConflict('Explicit room and faculty availability evidence is required.')


def operational(*, exclude_plan=None, date_from=None, date_to=None, revision_id=None):
    qs = m.PublishedOccurrence.objects.filter(
        **({'revision_id': revision_id} if revision_id else {'revision__status': 'PUBLISHED'})).select_related(
        'course_offering_section',
    )
    if date_from is not None and date_to is not None:
        moved = m.OccurrenceException.objects.filter(date__gte=date_from, date__lte=date_to).values('occurrence_id')
        qs = qs.filter(Q(date__gte=date_from, date__lte=date_to) | Q(pk__in=moved))
    if exclude_plan:
        qs = qs.exclude(revision__plan_id=exclude_plan)
    # Exceptions can move outside original dates, so bound after resolving overlays.
    result = []
    exceptions = {}
    for change in m.OccurrenceException.objects.filter(occurrence__in=qs).select_related('faculty_assignment').order_by('sequence'):
        exceptions[change.occurrence_id] = change
    # Operational membership follows M7 effective-dated episodes. Stored publication
    # snapshots remain unchanged; explicit revision history retains the original snapshot.
    episodes = {}
    if revision_id is None:
        for section_id, student_id, start, end in CourseOfferingSectionStudent.objects.filter(
                course_offering_section_id__in=qs.values('course_offering_section_id')).values_list(
                'course_offering_section_id','course_registration__term_registration__enrolment__student_id',
                'effective_from','effective_to'):
            episodes.setdefault(section_id,[]).append((student_id,start,end))
    for obj in qs:
        section = obj.course_offering_section
        item = Occurrence(obj.pk, obj.session_id, section.pk, obj.class_section_id,
            obj.class_batch_id, obj.employee_id, obj.room_id, obj.date,
            obj.start_time, obj.end_time, frozenset(obj.student_ids))
        change = exceptions.get(obj.pk)
        if change:
            if change.kind == 'CANCEL':
                continue
            item = replace(item, day=change.date, start=change.start_time, end=change.end_time,
                room_id=change.room_id, employee_id=change.faculty_assignment.employee_id)
        if item.section_id in episodes:
            known = {pk for pk, start, end in episodes[item.section_id]}
            current = {pk for pk, start, end in episodes[item.section_id] if start <= item.day and (end is None or item.day < end)}
            item = replace(item, students=(item.students - known) | frozenset(current))
        if (date_from is None or item.day >= date_from) and (date_to is None or item.day <= date_to):
            result.append(item)
    return result


def conflicts(left, right):
    if left.day != right.day or left.start >= right.end or right.start >= left.end:
        return ()
    resources = []
    for field, label in [('room_id', 'room'), ('employee_id', 'faculty')]:
        if getattr(left, field) is not None and getattr(left, field) == getattr(right, field):
            resources.append(label)
    if left.section_id == right.section_id:
        resources.append('course_section')
    if left.class_section_id == right.class_section_id and (left.batch_id is None or right.batch_id is None or left.batch_id == right.batch_id):
        resources.append('class_cohort')
    if left.students & right.students:
        resources.append('student_cohort')
    return tuple(resources)


def check_collisions(proposed, existing):
    by_date = {}
    for item in existing:
        by_date.setdefault(item.day, []).append(item)
    for item in proposed:
        for other in by_date.get(item.day, []):
            found = conflicts(item, other)
            if found:
                # Do not disclose the other tenant's identifiers or personal data.
                raise SchedulingConflict({'date': str(item.day), 'resources': list(found)})
        by_date.setdefault(item.day, []).append(item)


def check_contact_workload(rows, limit):
    totals = {}
    overrides = list(m.WorkloadOverride.objects.filter(employee_id__in={row.employee_id for row in rows}).order_by('-pk'))
    for item in rows:
        if item.employee_id is None:
            continue
        week = item.day.isocalendar()[:2]
        key = (item.employee_id, week)
        seconds = (item.end.hour * 3600 + item.end.minute * 60 + item.end.second
                   - item.start.hour * 3600 - item.start.minute * 60 - item.start.second)
        totals[key] = totals.get(key, Decimal(0)) + Decimal(seconds) / 3600
        allowed = next((override.weekly_limit for override in overrides
            if override.employee_id == item.employee_id and override.effective_from <= item.day <= override.effective_to), limit)
        if totals[key] > allowed:
            raise SchedulingConflict('Calculated weekly teaching hours exceed the institution limit.')
    return totals


def current_membership(section_id, day, snapshot_students):
    # Resolve M7 dated episodes without altering the publication snapshot.
    episodes=list(CourseOfferingSectionStudent.objects.filter(course_offering_section_id=section_id).values_list(
        'course_registration__term_registration__enrolment__student_id','effective_from','effective_to'))
    known={pk for pk,start,end in episodes}
    current={pk for pk,start,end in episodes if start<=day and (end is None or day<end)}
    return (frozenset(snapshot_students)-known)|frozenset(current)
