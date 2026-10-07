from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal
from datetime import date
from django.test import TransactionTestCase, override_settings
from django.db import close_old_connections, connections
from apps.academic_calendar.models import Semester
from apps.term_registration import models as reg
from apps.teaching_timetable import models as m, services as s
from apps.teaching_timetable.engine import SchedulingConflict
from . import test_services as fixtures


@override_settings(ADMISSION_ENROLMENT_ENABLED=True, PEOPLE_MASTER_ENABLED=True,
                   TERM_REGISTRATION_ENABLED=True, TEACHING_TIMETABLE_ENABLED=True)
class PublicationConcurrencyTests(TransactionTestCase):
    setUp = fixtures.TimetableTests.setUp
    session = fixtures.TimetableTests.session
    transition = fixtures.TimetableTests.transition

    def test_simultaneous_publications_cannot_double_book(self):
        self.session()
        self.transition('REVIEW')
        self.transition('APPROVED')
        other_offering = reg.ProgrammeTermOffering.objects.create(academic_term=self.term,
            programme=self.programme, curriculum_scheme=self.scheme,
            semester=Semester.objects.create(semester_number=2, semester_name='Second'),
            status='ACTIVE', created_by=self.root, updated_by=self.root)
        section = reg.ClassSection.objects.create(programme_term_offering=other_offering,
            section_code='B', capacity=1, created_by=self.root, updated_by=self.root)
        course = reg.CourseOffering.objects.create(programme_term_offering=other_offering,
            course=self.course, offering_code='M8B', status='ACTIVE', created_by=self.root, updated_by=self.root)
        mapping = reg.CourseOfferingSection.objects.create(programme_term_offering=other_offering,
            course_offering=course, class_section=section, session_type='LECTURE',
            created_by=self.root, updated_by=self.root)
        assignment = s.create_assignment(actor=self.root, values={
            'course_offering_section_id': mapping.pk, 'employee_id': self.employee.pk,
            'assignment_role': 'PRIMARY_INSTRUCTOR', 'workload_hours': Decimal('1'),
            'start_date': date(2026,9,1), 'end_date': date(2026,9,30)}, reason='Allocate')
        s.transition_assignment(actor=self.root, pk=assignment.pk, expected_version=1, target='ACTIVE', reason='Activate')
        other = s.create_revision(actor=self.root, offering_id=other_offering.pk, name='Other', reason='Plan')
        s.write_session(actor=self.root, revision_id=other.pk, expected_version=1, values={
            'course_offering_section_id': mapping.pk, 'faculty_assignment_id': assignment.pk,
            'room_id': self.room.pk, 'time_slot_id': self.slot.pk, 'day_of_week':1,
            'effective_from':date(2026,9,1), 'effective_to':date(2026,9,30)}, reason='Schedule')
        for target in ['REVIEW','APPROVED']:
            other.refresh_from_db()
            other = s.transition_revision(actor=self.root, pk=other.pk, expected_version=other.version, target=target, reason='Review')
        barrier = Barrier(2)
        def publish(pk, version):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                s.transition_revision(actor=self.root, pk=pk, expected_version=version, target='PUBLISHED', reason='Concurrent publication')
                return 'published'
            except SchedulingConflict:
                return 'conflict'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(publish, row.pk, row.version) for row in (self.revision, other)]
            results = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(results, ['published', 'conflict'])
        self.assertEqual(m.TimetableRevision.objects.filter(status='PUBLISHED').count(), 1)
        self.assertEqual(m.PublishedOccurrence.objects.count(), 4)
