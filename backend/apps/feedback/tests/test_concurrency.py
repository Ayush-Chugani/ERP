from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections,connections
from django.test import TransactionTestCase,override_settings
from . import test_services as fixtures
from apps.feedback import services as s,models as m
@override_settings(FEEDBACK_ENABLED=True,FEEDBACK_PRIVACY_KEY='test-only-feedback-key-000000000000000000',ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class SubmissionRaceTests(TransactionTestCase):
    setUp=fixtures.FeedbackTests.setUp
    activate=fixtures.FeedbackTests.activate
    cycle=fixtures.FeedbackTests.cycle
    student=fixtures.FeedbackTests.student
    answers=fixtures.FeedbackTests.answers
    def test_simultaneous_duplicate_submissions(self):
        self.cycle();user=self.student();answers=self.answers();barrier=Barrier(2)
        def submit(key):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                s.submit(actor=user,cycle_id=self.cycle_obj.pk,target={'course_offering_id':self.course_offering.pk},answers=answers,key=key);return 'saved'
            except s.Conflict:return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=[f.result(timeout=45) for f in [pool.submit(submit,'a'),pool.submit(submit,'b')]]
        self.assertCountEqual(results,['saved','conflict']);self.assertEqual(m.Response.objects.count(),1);self.assertEqual(m.SubmissionLedger.objects.count(),1)

    def test_close_and_submission_have_one_serial_order(self):
        self.cycle();user=self.student();answers=self.answers();barrier=Barrier(2)
        def work(action):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                if action=='close':
                    s.cycle_action(actor=self.root,pk=self.cycle_obj.pk,expected_version=self.cycle_obj.version,action='close',reason='Concurrent close')
                    return 'closed'
                s.submit(actor=user,cycle_id=self.cycle_obj.pk,target={'course_offering_id':self.course_offering.pk},answers=answers,key='race-close')
                return 'saved'
            except s.Conflict:return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=[f.result(timeout=45) for f in [pool.submit(work,'close'),pool.submit(work,'submit')]]
        self.assertIn('closed',results)
        self.cycle_obj.refresh_from_db();self.assertEqual(self.cycle_obj.status,'CLOSED')
        self.assertEqual(m.Response.objects.count(),1 if 'saved' in results else 0)
        self.assertEqual(m.Response.objects.count(),m.SubmissionLedger.objects.count())
