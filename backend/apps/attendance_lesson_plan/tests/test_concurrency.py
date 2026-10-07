from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase,override_settings
from django.db import close_old_connections,connections
from . import test_services as fixtures
from apps.attendance_lesson_plan import services as s,models as m

@override_settings(ATTENDANCE_ENABLED=True,ATTENDANCE_CALENDAR_ADAPTER='apps.attendance_lesson_plan.tests.test_services.instructional',ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class AttendanceConcurrencyTests(TransactionTestCase):
    setUp=fixtures.AttendanceTests.setUp
    session=fixtures.AttendanceTests.session
    transition=fixtures.AttendanceTests.transition
    publish=fixtures.AttendanceTests.publish
    change=fixtures.AttendanceTests.change
    opened=fixtures.AttendanceTests.opened
    finalized=fixtures.AttendanceTests.finalized
    student_actor=fixtures.AttendanceTests.student_actor
    def race(self,*actions):
        barrier=Barrier(2)
        def run(action):
            close_old_connections()
            try:
                barrier.wait(timeout=15);action();return 'saved'
            except s.Conflict:return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[f.result(timeout=45) for f in [pool.submit(run,a) for a in actions]]
        self.assertCountEqual(results,['saved','conflict'])
    def test_mark_finalize_and_reopen_races(self):
        row=self.opened();v=self.class_session.version
        def mark(status):return lambda:s.mark(actor=self.root,session_id=self.class_session.pk,expected_version=v,entries=[{'attendance_id':row.pk,'status_id':status.pk}],reason='Concurrent mark')
        self.race(mark(self.present),mark(self.absent))
        self.class_session.refresh_from_db();v=self.class_session.version
        def finalize():s.transition_session(actor=self.root,session_id=self.class_session.pk,expected_version=v,action='finalize',reason='Concurrent finalize')
        self.race(mark(self.present),finalize)
        self.class_session.refresh_from_db()
        if self.class_session.register_status!='FINALIZED':self.change('finalize')
        v=self.class_session.version
        def reopen():s.transition_session(actor=self.root,session_id=self.class_session.pk,expected_version=v,action='reopen',reason='Concurrent reopen')
        self.race(reopen,reopen)
    def test_correction_decision_race(self):
        row=self.finalized();student=self.student_actor()
        request=s.request_correction(actor=student,attendance_id=row.pk,expected_version=row.version,status_id=self.absent.pk,reason='Review')
        def decide():s.decide_correction(actor=self.root,correction_id=request.pk,expected_version=1,decision='APPROVED',reason='Verified')
        self.race(decide,decide)
        self.assertEqual(m.AuditEvent.objects.filter(action='attendance_corrected').count(),1)
