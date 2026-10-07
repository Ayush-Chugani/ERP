from datetime import date, time
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework.exceptions import NotFound, ValidationError
from apps.term_registration.tests import test_registration as registration_fixtures
from apps.term_registration import models as reg
from apps.people_master import models as people
from apps.curriculum_catalog.models import CourseCatalog, CourseCategory
from apps.organization.models import Building, Room
from apps.academic_calendar.models import TimeSlot
from apps.teaching_timetable import models as m, services as s
from apps.teaching_timetable.engine import operational, SchedulingConflict


@override_settings(ADMISSION_ENROLMENT_ENABLED=True, PEOPLE_MASTER_ENABLED=True,
                   TERM_REGISTRATION_ENABLED=True, TEACHING_TIMETABLE_ENABLED=True)
class TimetableTests(TestCase):
    def setUp(self):
        registration_fixtures.RegistrationTests.setUp(self)
        self.course = CourseCatalog.objects.create(owning_department=self.department,
            course_category=CourseCategory.objects.create(category_code='M8', category_name='M8'),
            course_code='M8', course_title='Timetable course', course_type='THEORY')
        self.course_offering = reg.CourseOffering.objects.create(programme_term_offering=self.offering,
            course=self.course, offering_code='M8', status='ACTIVE', created_by=self.root, updated_by=self.root)
        self.mapping = reg.CourseOfferingSection.objects.create(course_offering=self.course_offering,
            programme_term_offering=self.offering, class_section=self.section,
            session_type='LECTURE', created_by=self.root, updated_by=self.root)
        self.employee = people.Employee.objects.create(institution=self.institution,
            employment_source=self.source, employee_number='M8', first_name='Teacher',
            display_name='Teacher', employment_type='REGULAR', employment_status='ACTIVE', joining_date=date(2026, 1, 1))
        people.EmployeeAssignment.objects.create(employee=self.employee, campus=self.campus,
            department=self.department, designation=self.designation, start_date=date(2026, 1, 1))
        people.EmployeeCompetency.objects.create(employee=self.employee, course=self.course,
            competency_level='ADVANCED')
        self.room = Room.objects.create(building=Building.objects.create(campus=self.campus,
            building_code='M8', building_name='Teaching'), room_code='M8', room_type='CLASSROOM', capacity=30)
        self.slot = TimeSlot.objects.create(campus=self.campus, slot_code='M8', start_time=time(9), end_time=time(10))
        self.policy = s.configure_policy(actor=self.root, institution_id=self.institution.pk,
            values={'weekly_limit': Decimal('20')}, reason='Approved weekly workload policy')
        self.assignment = s.create_assignment(actor=self.root, values={
            'course_offering_section_id': self.mapping.pk, 'employee_id': self.employee.pk,
            'assignment_role': 'PRIMARY_INSTRUCTOR', 'workload_hours': Decimal('1'),
            'start_date': date(2026, 9, 1), 'end_date': date(2026, 9, 30)}, reason='Allocate instructor')
        self.assignment = s.transition_assignment(actor=self.root, pk=self.assignment.pk,
            expected_version=1, target='ACTIVE', reason='Ready to teach')
        self.revision = s.create_revision(actor=self.root, offering_id=self.offering.pk,
            name='September timetable', reason='Plan teaching')
        for field, pk in [('room_id', self.room.pk), ('employee_id', self.employee.pk)]:
            s.attest_availability(actor=self.root, values={field: pk, 'day_of_week': 1,
                'effective_from': date(2026, 9, 1), 'effective_to': date(2026, 9, 30),
                'start_time': time(8), 'end_time': time(18)}, reason='Availability confirmed')

    def session(self, **changes):
        values = {'course_offering_section_id': self.mapping.pk, 'faculty_assignment_id': self.assignment.pk,
            'room_id': self.room.pk, 'time_slot_id': self.slot.pk, 'day_of_week': 1,
            'effective_from': date(2026, 9, 1), 'effective_to': date(2026, 9, 30)}
        values.update(changes)
        self.revision.refresh_from_db()
        return s.write_session(actor=self.root, revision_id=self.revision.pk,
            expected_version=self.revision.version, values=values, reason='Schedule class')

    def transition(self, target):
        self.revision.refresh_from_db()
        self.revision = s.transition_revision(actor=self.root, pk=self.revision.pk,
            expected_version=self.revision.version, target=target, reason='Reviewed timetable')

    def publish(self):
        for target in ['REVIEW', 'APPROVED', 'PUBLISHED']:
            self.transition(target)

    def test_publication_snapshots_times_and_blocks_draft_edits(self):
        self.session()
        self.assertEqual(operational(), [])
        self.publish()
        self.assertEqual(len(operational()), 4)
        self.slot.start_time = time(8)
        self.slot.save()
        self.assertEqual(operational()[0].start, time(9))
        original_class = self.section.pk
        other_class = reg.ClassSection.objects.create(programme_term_offering=self.offering,
            section_code='MOVED', capacity=1, created_by=self.root, updated_by=self.root)
        reg.CourseOfferingSection.objects.filter(pk=self.mapping.pk).update(class_section=other_class)
        self.assertEqual(operational()[0].class_section_id, original_class)
        with self.assertRaises(SchedulingConflict):
            self.session()
        with self.assertRaises(ModelValidationError):
            m.PublishedOccurrence.objects.all().update(start_time=time(7))

    def test_overlapping_distinct_slot_is_rejected_atomically(self):
        self.session()
        overlap = TimeSlot.objects.create(campus=self.campus, slot_code='OVER', start_time=time(9, 30), end_time=time(10, 30))
        count = m.TimetableAudit.objects.count()
        with self.assertRaises(SchedulingConflict):
            self.session(time_slot_id=overlap.pk, effective_from=date(2026, 9, 10))
        self.assertEqual(m.TimetableSession.objects.count(), 1)
        self.assertEqual(m.TimetableAudit.objects.count(), count)

    def test_publication_requires_room_and_instructor(self):
        self.session(room_id=None, faculty_assignment_id=None)
        self.transition('REVIEW')
        with self.assertRaises(SchedulingConflict):
            self.transition('APPROVED')

    def test_publication_requires_availability(self):
        m.ResourceAvailability.objects.all().delete()
        self.session()
        self.transition('REVIEW')
        with self.assertRaises(SchedulingConflict):
            self.transition('APPROVED')

    def test_stale_revision_rejected(self):
        self.session()
        with self.assertRaises(SchedulingConflict):
            s.transition_revision(actor=self.root, pk=self.revision.pk, expected_version=1,
                target='REVIEW', reason='Stale review')

    def test_cancellation_retains_original_and_has_sequence_guard(self):
        self.session()
        self.publish()
        original = m.PublishedOccurrence.objects.order_by('date').first()
        values = {'kind': 'CANCEL', 'date': original.date, 'start_time': original.start_time,
            'end_time': original.end_time, 'room_id': self.room.pk,
            'faculty_assignment_id': self.assignment.pk}
        s.add_exception(actor=self.root, occurrence_id=original.pk, expected_sequence=0,
            values=values, reason='Holiday closure')
        self.assertEqual(len(operational()), 3)
        self.assertEqual(m.PublishedOccurrence.objects.count(), 4)
        with self.assertRaises(SchedulingConflict):
            s.add_exception(actor=self.root, occurrence_id=original.pk, expected_sequence=0,
                values=values, reason='Duplicate')

    def test_outbox_failure_rolls_back_publication(self):
        self.session()
        self.transition('REVIEW')
        self.transition('APPROVED')
        with patch.object(m.OutboxEvent.objects, 'create', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.transition('PUBLISHED')
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.status, 'APPROVED')
        self.assertFalse(m.PublishedOccurrence.objects.exists())

    @override_settings(TEACHING_TIMETABLE_ENABLED=False)
    def test_disabled_module_rejects_even_superuser(self):
        with self.assertRaises(NotFound):
            s.create_revision(actor=self.root, offering_id=self.offering.pk, name='No', reason='No')

    def test_composite_fk_rejects_cross_section_assignment(self):
        row = self.session()
        second = reg.ClassSection.objects.create(programme_term_offering=self.offering,
            section_code='B', capacity=1, created_by=self.root, updated_by=self.root)
        other = reg.CourseOfferingSection.objects.create(course_offering=self.course_offering,
            programme_term_offering=self.offering, class_section=second,
            session_type='LECTURE', created_by=self.root, updated_by=self.root)
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.TimetableSession.objects.filter(pk=row.pk).update(course_offering_section=other)

    def test_bulk_preview_quarantines_conflicts_without_writes(self):
        values = {'course_offering_section_id':self.mapping.pk, 'employee_id':self.employee.pk,
            'assignment_role':'TUTOR', 'workload_hours':Decimal('1'),
            'start_date':date(2026,9,1), 'end_date':date(2026,9,30)}
        count = m.TimetableAudit.objects.count()
        report = s.bulk_assignments(actor=self.root, rows=[values,values], dry_run=True, reason='Preview')
        self.assertEqual(len(report['conflicts']), 1)
        self.assertEqual(m.FacultyAssignment.objects.count(), 1)
        self.assertEqual(m.TimetableAudit.objects.count(), count)

    def test_authorized_workload_override_is_dated_and_immutable(self):
        self.policy.weekly_limit = Decimal('1')
        self.policy.save()
        values = {'course_offering_section_id':self.mapping.pk, 'employee_id':self.employee.pk,
            'assignment_role':'TUTOR', 'workload_hours':Decimal('2'),
            'start_date':date(2026,9,1), 'end_date':date(2026,9,30)}
        with self.assertRaises(SchedulingConflict):
            s.create_assignment(actor=self.root, values=values, reason='Over limit')
        grant = s.approve_workload_override(actor=self.root, values={'employee_id':self.employee.pk,
            'effective_from':date(2026,8,31),'effective_to':date(2026,10,4),
            'weekly_limit':Decimal('3')}, reason='Authorized temporary increase')
        self.assertEqual(s.create_assignment(actor=self.root, values=values, reason='Within override').workload_hours, Decimal('2'))
        with self.assertRaises(ModelValidationError):
            grant.reason='Rewrite'; grant.save()
