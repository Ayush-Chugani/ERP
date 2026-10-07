from datetime import date
from django.test import TestCase, override_settings
from . import test_services as fixtures
from apps.teaching_timetable import models as m, solver
from apps.teaching_timetable.engine import SchedulingConflict
from apps.teaching_timetable.integrations import consume


@override_settings(ADMISSION_ENROLMENT_ENABLED=True, PEOPLE_MASTER_ENABLED=True,
                   TERM_REGISTRATION_ENABLED=True, TEACHING_TIMETABLE_ENABLED=True)
class SolverTests(TestCase):
    setUp = fixtures.TimetableTests.setUp

    def choices(self):
        return [[{'course_offering_section_id': self.mapping.pk,
            'faculty_assignment_id': self.assignment.pk, 'room_id': self.room.pk,
            'time_slot_id': self.slot.pk, 'day_of_week': 1,
            'effective_from': '2026-09-01', 'effective_to': '2026-09-30'}]]

    def queue(self):
        return solver.queue_job(actor=self.root, revision_id=self.revision.pk,
            expected_version=1, choices=self.choices(), seed=42, reason='Generate')

    def test_generation_is_deterministic_and_acceptance_is_explicit(self):
        job = self.queue()
        self.assertEqual(solver.solve(job.input_snapshot,42), solver.solve(job.input_snapshot,42))
        self.assertTrue(solver.run_next())
        job.refresh_from_db()
        self.assertEqual(job.status, 'SUCCEEDED')
        self.assertFalse(m.TimetableSession.objects.exists())
        solver.accept_job(actor=self.root, pk=job.pk, expected_version=job.version, reason='Accept reviewed candidate')
        self.assertEqual(m.TimetableSession.objects.count(), 1)
        self.assertFalse(m.PublishedOccurrence.objects.exists())

    def test_changed_revision_rejects_stale_candidate(self):
        job = self.queue()
        solver.run_next()
        job.refresh_from_db()
        self.revision.version += 1
        self.revision.save()
        with self.assertRaises(SchedulingConflict):
            solver.accept_job(actor=self.root, pk=job.pk, expected_version=job.version, reason='Stale')

    def test_cancelled_job_is_not_processed(self):
        job = self.queue()
        solver.cancel_job(actor=self.root, pk=job.pk, expected_version=1, reason='Cancel request')
        self.assertFalse(solver.run_next())

    def test_outbox_consumption_retries_and_deduplicates(self):
        seen = []
        count = consume('test', lambda event: seen.append(str(event.event_id)))
        self.assertGreater(count, 0)
        self.assertEqual(consume('test', lambda event: seen.append(str(event.event_id))), 0)
        self.assertEqual(len(seen), len(set(seen)))
        def failed(event):
            raise RuntimeError('delivery interrupted')
        with self.assertRaises(RuntimeError):
            consume('failing', failed)
        self.assertFalse(m.EventReceipt.objects.filter(consumer='failing').exists())
