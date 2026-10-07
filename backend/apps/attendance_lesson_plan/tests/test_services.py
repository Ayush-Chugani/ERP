from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.db import transaction,IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError,PermissionDenied,NotFound
from rest_framework.test import APIClient
from apps.teaching_timetable.tests import test_services as upstream
from apps.teaching_timetable.models import PublishedOccurrence
from apps.term_registration import models as reg
from apps.tenancy.models import InstitutionModule,Membership,ScopeGrant
from apps.people_master.models import AccountLink
from apps.attendance_lesson_plan import models as m,services as s,commands as c,selectors as q

def instructional(**kwargs):return {'status':'INSTRUCTIONAL','reference':'test-calendar'}

@override_settings(ATTENDANCE_ENABLED=True,ATTENDANCE_CALENDAR_ADAPTER='apps.attendance_lesson_plan.tests.test_services.instructional',
 ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class AttendanceTests(TestCase):
    session=upstream.TimetableTests.session
    transition=upstream.TimetableTests.transition
    publish=upstream.TimetableTests.publish
    def setUp(self):
        upstream.TimetableTests.setUp(self)
        for code in ["PRESENT","ABSENT","LATE","EXCUSED","ON_DUTY"]:
            m.AttendanceStatus.objects.get_or_create(status_code=code,defaults={"status_name":code.title(),"counts_as_present":code=="PRESENT"})
        term=reg.StudentTermRegistration.objects.create(enrolment=self.enrolment,programme=self.programme,programme_term_offering=self.offering,class_section=self.section,registration_date=date(2026,9,1),registration_status='APPROVED',created_by=self.root,updated_by=self.root)
        course=reg.StudentCourseRegistration.objects.create(term_registration=term,programme_term_offering=self.offering,course_offering=self.course_offering,registration_date=date(2026,9,1),registration_status='APPROVED',created_by=self.root,updated_by=self.root)
        self.roster=reg.CourseOfferingSectionStudent.objects.create(course_registration=course,course_offering=self.course_offering,course_offering_section=self.mapping,session_type='LECTURE',effective_from=date(2026,9,1),created_by=self.root,updated_by=self.root)
        self.session();self.publish()
        self.occurrence=PublishedOccurrence.objects.order_by('date').first()
        self.attendance_policy=s.configure_policy(actor=self.root,section_id=self.mapping.pk,expected_number=0,basis='SESSION',rules={'PRESENT':{'credit':1,'denominator':1},'ABSENT':{'credit':0,'denominator':1},'LATE':{'credit':'.5','denominator':1}},threshold=75,edit_days=365,correction_days=365,reason='Approved test policy')
        self.class_session=s.create_session(actor=self.root,section_id=self.mapping.pk,occurrence_id=self.occurrence.pk,reason='Published occurrence')
        self.present=m.AttendanceStatus.objects.get(status_code='PRESENT');self.absent=m.AttendanceStatus.objects.get(status_code='ABSENT')
    def change(self,action,actor=None):
        self.class_session.refresh_from_db()
        self.class_session=s.transition_session(actor=actor or self.root,session_id=self.class_session.pk,expected_version=self.class_session.version,action=action,reason='Test '+action)
        return self.class_session
    def opened(self):
        self.change('conduct');self.change('open')
        return m.StudentAttendance.objects.get(class_session=self.class_session)
    def finalized(self):
        row=self.opened()
        s.mark(actor=self.root,session_id=self.class_session.pk,expected_version=self.class_session.version,entries=[{'attendance_id':row.pk,'status_id':self.present.pk}],reason='Mark')
        self.change('finalize');row.refresh_from_db();return row
    def student_actor(self):
        user=get_user_model().objects.create_user(username='attendance-student')
        InstitutionModule.objects.filter(institution=self.institution).update(attendance_lesson_plan=True)
        Membership.objects.create(user=user,institution=self.institution)
        AccountLink.objects.create(user=user,student=self.enrolment.student)
        return user
    def test_generation_retry_and_snapshot(self):
        again=s.create_session(actor=self.root,section_id=self.mapping.pk,occurrence_id=self.occurrence.pk,reason='Retry')
        self.assertEqual(again.pk,self.class_session.pk)
        s.configure_policy(actor=self.root,section_id=self.mapping.pk,expected_number=1,basis='DURATION',rules={'PRESENT':{'credit':1,'denominator':1}},threshold=90,edit_days=0,correction_days=0,reason='New policy')
        self.assertEqual(self.class_session.policy_id,self.attendance_policy.pk)
    def test_unmarked_is_not_absent(self):
        row=self.opened()
        self.assertIsNone(row.attendance_status_id)
        with self.assertRaises(s.Conflict):self.change('finalize')
        self.assertFalse(m.StudentAttendance.objects.exclude(attendance_status=None).exists())
    def test_bulk_rollback_stale_and_policy_report(self):
        row=self.opened();v=self.class_session.version
        with self.assertRaises(NotFound):
            s.mark(actor=self.root,session_id=self.class_session.pk,expected_version=v,entries=[{'attendance_id':row.pk,'status_id':self.present.pk},{'attendance_id':999999,'status_id':self.present.pk}],reason='Atomic')
        row.refresh_from_db();self.assertIsNone(row.attendance_status_id)
        s.mark(actor=self.root,session_id=self.class_session.pk,expected_version=v,entries=[{'attendance_id':row.pk,'status_id':self.present.pk}],reason='Mark')
        with self.assertRaises(s.Conflict):s.mark(actor=self.root,session_id=self.class_session.pk,expected_version=v,entries=[{'attendance_id':row.pk,'status_id':self.absent.pk}],reason='Stale')
        self.change('finalize')
        self.assertEqual(q.report(self.root,date(2026,9,1),date(2026,9,30))[0]['percentage'],'100.00')
    def test_roster_change_blocks_finalization_without_deleting_marks(self):
        row=self.opened()
        self.roster.effective_from=date(2026,9,8);self.roster.save()
        with self.assertRaises(s.Conflict):self.change('finalize')
        self.assertTrue(m.StudentAttendance.objects.filter(pk=row.pk).exists())
    def test_correction_separate_reviewer_and_once_only(self):
        row=self.finalized();student=self.student_actor()
        correction=s.request_correction(actor=student,attendance_id=row.pk,expected_version=row.version,status_id=self.absent.pk,reason='Review')
        s.decide_correction(actor=self.root,correction_id=correction.pk,expected_version=1,decision='APPROVED',reason='Evidence verified')
        row.refresh_from_db();self.assertEqual(row.credit,0)
        self.assertEqual(q.report(self.root,date(2026,9,1),date(2026,9,30))[0]['percentage'],'0.00')
        with self.assertRaises(s.Conflict):s.decide_correction(actor=self.root,correction_id=correction.pk,expected_version=1,decision='APPROVED',reason='Retry without receipt')
        row.refresh_from_db()
        own=s.request_correction(actor=self.root,attendance_id=row.pk,expected_version=row.version,status_id=self.present.pk,reason='Request')
        with self.assertRaises(PermissionDenied):s.decide_correction(actor=self.root,correction_id=own.pk,expected_version=1,decision='APPROVED',reason='Self review')
    def test_correction_stale_and_pending_uniqueness(self):
        row=self.finalized();student=self.student_actor()
        correction=s.request_correction(actor=student,attendance_id=row.pk,expected_version=row.version,status_id=self.absent.pk,reason='Request')
        with self.assertRaises(s.Conflict):s.request_correction(actor=student,attendance_id=row.pk,expected_version=row.version,status_id=self.absent.pk,reason='Duplicate')
        m.StudentAttendance.objects.filter(pk=row.pk).update(version=row.version+1)
        with self.assertRaises(s.Conflict):s.decide_correction(actor=self.root,correction_id=correction.pk,expected_version=1,decision='APPROVED',reason='Stale')
        correction.refresh_from_db();self.assertEqual(correction.request_status,'PENDING')
    def test_lesson_coverage_and_immutable_revisions(self):
        self.change('conduct')
        lesson=s.revise_lessons(actor=self.root,section_id=self.mapping.pk,expected_number=0,topics=[{'key':'T1','title':'Introduction','planned_date':date(2026,9,7),'minutes':60,'method':'Lecture','outcomes':'Understand'}],reason='Plan')
        s.record_coverage(actor=self.root,session_id=self.class_session.pk,expected_version=self.class_session.version,lesson_revision_id=lesson.pk,topic_key='T1',percent=Decimal('50'),minutes=30,reason='Partial')
        self.class_session.refresh_from_db()
        with self.assertRaises(s.Conflict):s.record_coverage(actor=self.root,session_id=self.class_session.pk,expected_version=self.class_session.version,lesson_revision_id=lesson.pk,topic_key='T1',percent=Decimal('60'),minutes=20,reason='Over coverage')
        from django.core.exceptions import ValidationError as ModelError
        with self.assertRaises(ModelError):m.LessonRevision.objects.filter(pk=lesson.pk).update(reason='Rewrite')
    def test_database_rejects_wrong_roster_section(self):
        row=self.opened()
        section=reg.ClassSection.objects.create(programme_term_offering=self.offering,section_code='B',created_by=self.root,updated_by=self.root)
        mapping=reg.CourseOfferingSection.objects.create(course_offering=self.course_offering,programme_term_offering=self.offering,class_section=section,session_type='LECTURE',created_by=self.root,updated_by=self.root)
        with self.assertRaises(IntegrityError),transaction.atomic():m.StudentAttendance.objects.filter(pk=row.pk).update(course_offering_section=mapping)
        with self.assertRaises(IntegrityError),transaction.atomic():m.ClassSession.objects.filter(pk=self.class_session.pk).update(course_offering_section=mapping)
    def test_idempotency_api_and_disabled(self):
        client=APIClient();client.force_authenticate(self.root)
        data={'session_id':self.class_session.pk,'expected_version':1,'action':'conduct','reason':'Conduct'}
        first=client.post('/api/v1/attendance/commands/transition-session/',data,format='json',HTTP_IDEMPOTENCY_KEY='same')
        self.assertEqual(first.status_code,200,first.data)
        self.assertEqual(client.post('/api/v1/attendance/commands/transition-session/',data,format='json',HTTP_IDEMPOTENCY_KEY='same').data,first.data)
        self.assertEqual(first['Cache-Control'],'private, no-store')
        with override_settings(ATTENDANCE_ENABLED=False):self.assertEqual(client.get('/api/v1/attendance/sessions/').status_code,403)
    def test_student_cannot_view_other_register(self):
        row=self.finalized();student=self.student_actor();client=APIClient();client.force_authenticate(student)
        self.assertEqual(client.get('/api/v1/attendance/mine/').data['count'],1)
        self.assertEqual(client.get(f'/api/v1/attendance/register/{self.class_session.pk}/').status_code,404)
        self.assertEqual(client.get('/api/v1/attendance/sessions/').status_code,403)
    def test_outbox_failure_rolls_back(self):
        with patch.object(m.OutboxEvent.objects,'create',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.change('conduct')
        self.class_session.refresh_from_db();self.assertEqual(self.class_session.session_status,'PLANNED')
    def test_calendar_provider_unavailable(self):
        with override_settings(ATTENDANCE_CALENDAR_ADAPTER=''):
            occurrence=PublishedOccurrence.objects.order_by('date')[1]
            with self.assertRaises(s.Conflict):s.create_session(actor=self.root,section_id=self.mapping.pk,occurrence_id=occurrence.pk,reason='No calendar')

    def test_explicit_reconciliation_preserves_excluded_evidence(self):
        row=self.opened()
        self.roster.effective_from=date(2026,9,8);self.roster.save()
        s.reconcile_register(actor=self.root,session_id=self.class_session.pk,expected_version=self.class_session.version,reason='Reviewed roster date')
        row.refresh_from_db();self.assertFalse(row.is_eligible)
        self.assertEqual(row.exclusion_reason,'Reviewed roster date')
        self.change('finalize');row.refresh_from_db()
        self.assertEqual(row.denominator,0)

    def test_session_allowlist_and_revocation(self):
        from django.contrib.auth.models import Permission
        user=get_user_model().objects.create_user(username='attendance-reviewer')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='attendance_lesson_plan'))
        InstitutionModule.objects.filter(institution=self.institution).update(attendance_lesson_plan=True)
        membership=Membership.objects.create(user=user,institution=self.institution)
        grant=ScopeGrant.objects.create(membership=membership,role='INSTITUTION_ADMIN',record_limits={'attendance-sessions':[]})
        self.assertFalse(q.sessions(user).exists())
        with self.assertRaises(NotFound):q.register(user,self.class_session.pk)
        grant.record_limits={'attendance-sessions':[self.class_session.pk]};grant.save()
        self.assertEqual(q.sessions(user).count(),1)
        grant.is_active=False;grant.save()
        self.assertFalse(q.sessions(user).exists())

    def test_batch_dry_run_and_health(self):
        import json,tempfile
        from pathlib import Path
        from io import StringIO
        from django.core.management import call_command
        row=self.opened()
        data=[{'operation':'mark','key':'mapped-source-1','data':{'session_id':self.class_session.pk,'expected_version':self.class_session.version,'entries':[{'attendance_id':row.pk,'status_id':self.present.pk}],'reason':'Mapped import'}}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mapped.json';path.write_text(json.dumps(data),encoding='utf-8')
            output=StringIO();call_command('attendance_batch',str(path),actor=self.root.pk,stdout=output)
            self.assertFalse(json.loads(output.getvalue())['committed'])
            row.refresh_from_db();self.assertIsNone(row.attendance_status_id)
            call_command('attendance_batch',str(path),actor=self.root.pk,apply=True,stdout=StringIO())
            row.refresh_from_db();self.assertEqual(row.attendance_status_id,self.present.pk)
        output=StringIO();call_command('attendance_health',actor=self.root.pk,stdout=output)
        self.assertGreater(json.loads(output.getvalue())['undelivered_events'],0)
