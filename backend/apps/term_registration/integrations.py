"""Explicit eligibility adapters. Missing evidence never implies eligibility."""
from django.conf import settings
from django.utils.module_loading import import_string
from .services import RegistrationConflict


def require_eligibility(term, course, kind):
    adapter = getattr(settings,'REGISTRATION_ELIGIBILITY_ADAPTER','')
    if not adapter:
        raise RegistrationConflict('Course eligibility evidence is unavailable. Configure the result/attempt/prerequisite adapter.')
    result = import_string(adapter)(term_registration=term,course_offering=course,registration_type=kind)
    if not isinstance(result,dict) or result.get('status') != 'ELIGIBLE' or not result.get('reference'):
        raise RegistrationConflict('Course eligibility is unavailable or not satisfied.')
    return result


def require_timetable(registration, mapping, effective_date):
    from apps.tenancy.models import InstitutionModule
    from apps.teaching_timetable.engine import operational
    from apps.teaching_timetable.models import TimetableRevision
    from .models import CourseOfferingSectionStudent
    from .selectors import as_of_roster
    offering = registration.programme_term_offering
    institution_id = offering.programme.department.campus.institution_id
    if not getattr(settings,'TEACHING_TIMETABLE_ENABLED',False) or not InstitutionModule.objects.filter(institution_id=institution_id,teaching_timetable=True).exists():
        raise RegistrationConflict('Timetable eligibility is unavailable until M8 is enabled for this institution.')
    if not TimetableRevision.objects.filter(plan__programme_term_offering=offering,status='PUBLISHED').exists():
        raise RegistrationConflict('Publish a timetable before assigning operational roster membership.')
    occurrences = operational(date_from=effective_date,date_to=offering.academic_term.end_date)
    proposed = [row for row in occurrences if row.section_id == mapping.pk]
    if not proposed: raise RegistrationConflict('No published sessions exist for this mapping.')
    student_id = registration.term_registration.enrolment.student_id
    episodes = CourseOfferingSectionStudent.objects.filter(course_registration__term_registration__enrolment__student_id=student_id)
    for left in proposed:
        other_sections = set(as_of_roster(episodes,left.day).values_list('course_offering_section_id',flat=True))
        for right in occurrences:
            if right.section_id == mapping.pk: continue
            if (right.section_id in other_sections or student_id in right.students or str(student_id) in right.students) and left.day == right.day and left.start < right.end and right.start < left.end:
                raise RegistrationConflict('Published timetable sessions clash for this student.')
        from apps.organization.models import Room
        capacity = Room.objects.get(pk=left.room_id).capacity
        enrolled = as_of_roster(CourseOfferingSectionStudent.objects.filter(course_offering_section=mapping),left.day).count()
        if capacity is not None and enrolled + 1 > capacity:
            raise RegistrationConflict('Published room capacity would be exceeded.')


def deliver(consumer, callback, limit=100):
    """Callback must be a local transactional consumer or deduplicate by event ID."""
    from django.db import transaction
    from .models import RegistrationEvent, EventDelivery
    count = 0
    for event_id in RegistrationEvent.objects.exclude(eventdelivery__consumer=consumer).order_by('pk').values_list('pk',flat=True)[:limit]:
        with transaction.atomic():
            event = RegistrationEvent.objects.select_for_update().get(pk=event_id)
            if EventDelivery.objects.filter(event=event,consumer=consumer).exists(): continue
            callback(str(event.pk),event.event_type,event.payload)
            EventDelivery.objects.create(event=event,consumer=consumer)
            count += 1
    return count
