from apps.people_master.models import AccountLink
from django.db.models import Q
from . import models as m
from .policies import programmes, grants, enabled
from .engine import operational


def published_occurrences(actor, date_from, date_to):
    """Authorized operational rows for attendance, calendars and UI; never drafts."""
    if not enabled(actor, 'view_schedule'):
        return []
    allowed = set(read_queryset(actor, 'sessions', 'view_schedule').values_list('pk', flat=True))
    institutions = set(grants(actor).values_list('membership__institution_id', flat=True))
    links = list(AccountLink.objects.filter(user=actor))
    employees = {link.employee_id for link in links if link.employee_id}
    students = {link.student_id for link in links if link.student_id}
    session_institutions = dict(m.TimetableSession.objects.filter(revision__status='PUBLISHED').values_list(
        'pk', 'revision__plan__programme_term_offering__programme__department__campus__institution_id'))
    from apps.people_master.models import Employee
    from apps.organization.models import Room
    session_labels = dict(m.TimetableSession.objects.filter(revision__status='PUBLISHED').values_list(
        'pk', 'course_offering_section__course_offering__course__course_title'))
    employee_labels = dict(Employee.objects.values_list('pk', 'display_name'))
    room_labels = dict(Room.objects.values_list('pk', 'room_code'))
    rows = []
    sequences = {}
    for occurrence_id, sequence in m.OccurrenceException.objects.filter(occurrence__revision__status='PUBLISHED').order_by('sequence').values_list('occurrence_id', 'sequence'):
        sequences[occurrence_id] = sequence
    for item in operational(date_from=date_from, date_to=date_to):
        if item.session_id not in allowed and not (session_institutions.get(item.session_id) in institutions
            and (item.employee_id in employees or item.students & students)):
            continue
        sequence = sequences.get(item.identity, 0)
        rows.append({'id': str(item.identity), 'session_id': str(item.session_id),
            'course_offering_section_id': str(item.section_id), 'class_section_id': str(item.class_section_id),
            'batch_id': str(item.batch_id) if item.batch_id else None,
            'employee_id': str(item.employee_id), 'room_id': str(item.room_id),
            'date': str(item.day), 'start_time': str(item.start), 'end_time': str(item.end),
            'sequence': sequence, 'course_label': session_labels.get(item.session_id, ''),
            'employee_label': employee_labels.get(item.employee_id, ''),
            'room_label': room_labels.get(item.room_id, '')})
    return sorted(rows, key=lambda row: (row['date'], row['start_time'], row['id']))


READS = {
    'assignments': (m.FacultyAssignment, 'course_offering_section__programme_term_offering__programme',
        ['course_offering_section_id', 'employee_id', 'assignment_role', 'workload_hours', 'start_date', 'end_date', 'assignment_status']),
    'revisions': (m.TimetableRevision, 'plan__programme_term_offering__programme', ['plan_id', 'number', 'status']),
    'sessions': (m.TimetableSession, 'revision__plan__programme_term_offering__programme',
        ['revision_id', 'course_offering_section_id', 'faculty_assignment_id', 'room_id', 'time_slot_id', 'day_of_week', 'effective_from', 'effective_to']),
    'jobs': (m.SolverJob, 'revision__plan__programme_term_offering__programme', ['revision_id', 'status', 'seed', 'result']),
}


def read_queryset(actor, resource, action='manage_timetable'):
    model, path, _ = READS[resource]
    qs = model.objects.filter(**{path + '__in': programmes(actor, action)})
    if actor.is_superuser:
        return qs.order_by('pk')
    references = {'assignments': {'employees': 'employee_id'}, 'sessions': {
        'employees': 'faculty_assignment__employee_id', 'rooms': 'room_id', 'time-slots': 'time_slot_id'}}.get(resource, {})
    condition = Q(pk__in=[])
    for grant in grants(actor).filter(role__in=['INSTITUTION_ADMIN', 'CAMPUS_ADMIN', 'DEPARTMENT_ADMIN']):
        part = Q(**{path + '__department__campus__institution_id': grant.membership.institution_id})
        if grant.campus_id:
            part &= Q(**{path + '__department__campus_id': grant.campus_id})
        if grant.department_id:
            part &= Q(**{path + '__department_id': grant.department_id})
        if not isinstance(grant.record_limits, dict):
            continue
        valid = True
        for name, field in {'programmes': path, **references}.items():
            if name not in grant.record_limits:
                continue
            ids = grant.record_limits[name]
            if not isinstance(ids, list) or any(type(pk) is not int or pk < 1 for pk in ids):
                valid = False
                break
            part &= Q(**{field + '__in': ids}) | Q(**{field + '__isnull': True})
        if valid:
            condition |= part
    return qs.filter(condition).order_by('pk')


def read_record(obj, fields):
    result = {'id': str(obj.pk), 'version': obj.version}
    for field in fields:
        value = getattr(obj, field)
        result[field] = str(value) if value is not None and (field.endswith('_id') or field == 'workload_hours') else value
    return result
