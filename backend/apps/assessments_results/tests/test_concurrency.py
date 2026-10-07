from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase,override_settings
from django.db import close_old_connections,connections
from . import test_domain as fixtures
from apps.assessments_results import services as s,models as m
@override_settings(ASSESSMENTS_RESULTS_ENABLED=True,ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class ConcurrencyTests(TransactionTestCase):
    setUp=fixtures.AssessmentTests.setUp
    transition=fixtures.AssessmentTests.transition
    marks=fixtures.AssessmentTests.marks
    published_event=fixtures.AssessmentTests.published_event
    calculate=fixtures.AssessmentTests.calculate
    def race(self,one,two):
        barrier=Barrier(2)
        def run(fn):
            close_old_connections()
            try:barrier.wait(timeout=15);fn();return 'saved'
            except s.Conflict:return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=[f.result(timeout=45) for f in [pool.submit(run,one),pool.submit(run,two)]]
        self.assertCountEqual(results,['saved','conflict'])
    def test_atomic_mark_and_publication_race(self):
        self.transition('conduct');self.marks();version=self.event.version
        def mark():s.mark(actor=self.root,event_id=self.event.pk,expected_version=version,entries=[{'course_registration_id':self.registration.pk,'attendance_status':'ABSENT'}],reason='Concurrent mark')
        def publish():s.transition_event(actor=self.reviewer,pk=self.event.pk,expected_version=version,action='publish',reason='Concurrent publication')
        self.race(mark,publish)
    def test_result_publication_race(self):
        self.published_event();result=self.calculate()
        def publish():s.transition_result(actor=self.reviewer,resource='course',pk=result.pk,expected_version=result.version,action='publish',reason='Concurrent publication')
        self.race(publish,publish)
        self.assertEqual(m.Publication.objects.filter(resource='studentcourseresult').count(),1)
