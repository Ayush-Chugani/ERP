from django.apps import apps
from django.core.checks import Error, Tags, register


@register(Tags.models)
def upstream_contracts(app_configs, **kwargs):
    errors = []
    for label, key in [('term_registration.CourseOfferingSection', 'course_offering_section_id'),
        ('people_master.Employee', 'employee_id'), ('organization.Room', 'room_id'),
        ('academic_calendar.TimeSlot', 'time_slot_id')]:
        try:
            model = apps.get_model(label)
        except LookupError:
            errors.append(Error('M8 requires ' + label, id='teaching_timetable.E001'))
            continue
        if model._meta.pk.name != key:
            errors.append(Error('M8 upstream primary key mismatch: ' + label, id='teaching_timetable.E002'))
    return errors
