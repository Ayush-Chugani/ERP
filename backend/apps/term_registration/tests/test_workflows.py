from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError
from . import test_registration as fixtures
from apps.term_registration import models as m, services as s, workflows as w, execution as e
from apps.curriculum_catalog.models import CourseCatalog, CourseCategory, CurriculumCourse


def eligible(**kwargs):
    return {'status':'ELIGIBLE','reference':'test-results-1'}


@override_settings(ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,
    REGISTRATION_ELIGIBILITY_ADAPTER='apps.term_registration.tests.test_workflows.eligible')
class WorkflowTests(TestCase):
    def setUp(self):
        fixtures.RegistrationTests.setUp(self)
        self.catalog=CourseCatalog.objects.create(owning_department=self.department,course_category=CourseCategory.objects.create(category_code='M7',category_name='M7'),course_code='M7',course_title='Course',course_type='THEORY',credits=3)
        self.curriculum=CurriculumCourse.objects.create(curriculum_scheme=self.scheme,semester=self.semester,course=self.catalog,course_category=self.catalog.course_category)
        self.policy=w.configure_policy(actor=self.root,programme_id=self.programme.pk,minimum_credits=0,maximum_credits=12,reason='Institution policy')
        self.course=w.create_course(actor=self.root,values={'programme_term_offering_id':self.offering.pk,'curriculum_course_id':self.curriculum.pk,'course_id':self.catalog.pk,'offering_code':'M7'},reason='Offer curriculum')
        self.mapping=w.create_mapping(actor=self.root,values={'course_offering_id':self.course.pk,'class_section_id':self.section.pk,'session_type':'LECTURE'},reason='Teach class')
        self.course=w.transition_course(actor=self.root,pk=self.course.pk,expected_version=1,target='OPEN',reason='Open')
    draft=fixtures.RegistrationTests.draft
    approve=fixtures.RegistrationTests.approve
    register=fixtures.RegistrationTests.register

    def registered(self):
        row=self.draft();self.approve();return self.register(row)

    def course_registration(self):
        row=self.registered()
        with patch('apps.term_registration.integrations.require_timetable'):
            return w.register_course(actor=self.root,term_id=row.pk,course_id=self.course.pk,registration_type='REGULAR',reason='Register course')

    def approved_course(self):
        row=self.course_registration()
        return w.transition_registration(actor=self.root,pk=row.pk,expected_version=1,target='APPROVED',effective_date=timezone.localdate(),reason='Approve')

    def test_offering_setup_and_applicability(self):
        from apps.academic_calendar.models import AcademicTerm
        term=AcademicTerm.objects.create(academic_year=self.year,term_code='NEW',term_name='Next',term_type='EVEN',start_date=self.term.start_date,end_date=self.term.end_date,status='REGISTRATION_OPEN',registration_start_date=self.term.start_date,registration_end_date=self.term.end_date)
        row=w.create_offering(actor=self.root,values={'programme_id':self.programme.pk,'academic_term_id':term.pk,'curriculum_scheme_id':self.scheme.pk,'semester_id':self.semester.pk},reason='New offering')
        w.save_group(actor=self.root,resource='sections',values={'programme_term_offering_id':row.pk,'section_code':'A','capacity':10},reason='Create section')
        row=w.transition_offering(actor=self.root,pk=row.pk,expected_version=1,target='REGISTRATION_OPEN',reason='Open')
        self.assertEqual(row.status,'REGISTRATION_OPEN')
        self.scheme.status='RETIRED';self.scheme.save()
        row.refresh_from_db()
        with self.assertRaises(s.RegistrationConflict): w.validate_offering(row)

    def test_idempotency_dry_run_and_all_or_nothing(self):
        data={'offering_id':self.offering.pk,'enrolment_id':self.enrolment.pk}
        first=e.execute(actor=self.root,operation='create-draft',data=data,key='draft')
        self.assertEqual(first,e.execute(actor=self.root,operation='create-draft',data=data,key='draft'))
        with self.assertRaises(s.RegistrationConflict): e.execute(actor=self.root,operation='create-draft',data={**data,'section_id':self.section.pk},key='draft')
        rows=[{'operation':'save-section','data':{'programme_term_offering_id':self.offering.pk,'section_code':'B','reason':'Import'}}]
        e.bulk(actor=self.root,rows=rows,key='import',dry_run=True)
        self.assertFalse(m.ClassSection.objects.filter(section_code='B').exists())
        self.assertFalse(m.CommandReceipt.objects.filter(key='import:0').exists())
        with self.assertRaises(ValidationError):
            e.bulk(actor=self.root,rows=rows+[{'operation':'invalid','data':{}}],key='bad',dry_run=False)
        self.assertFalse(m.ClassSection.objects.filter(section_code='B').exists())
        e.bulk(actor=self.root,rows=rows,key='import',dry_run=False)
        self.assertTrue(m.ClassSection.objects.filter(section_code='B').exists())

    def test_balanced_allocation_and_stale_updates(self):
        row=s.create_draft(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk)
        row=w.allocate(actor=self.root,pk=row.pk,expected_version=1,automatic=True,reason='Balance')
        self.assertEqual(row.class_section_id,self.section.pk)
        with self.assertRaises(s.RegistrationConflict): w.allocate(actor=self.root,pk=row.pk,expected_version=1,section_id=self.section.pk,reason='Stale')
        with self.assertRaises(ValidationError): w.allocate(actor=self.root,pk=row.pk,expected_version=2,automatic=True,reason='Do not overwrite')

    def test_capacity_update_cannot_erase_reservations(self):
        self.registered()
        with self.assertRaises(s.RegistrationConflict):
            w.save_group(actor=self.root,resource='sections',pk=self.section.pk,expected_version=1,values={'is_active':False},reason='Deactivate')

    def test_credit_limit_and_missing_adapter_fail_closed(self):
        row=self.registered()
        with override_settings(REGISTRATION_ELIGIBILITY_ADAPTER=''):
            with self.assertRaises(s.RegistrationConflict):
                w.register_course(actor=self.root,term_id=row.pk,course_id=self.course.pk,registration_type='REGULAR',reason='No evidence')
        m.RegistrationPolicy.objects.filter(pk=self.policy.pk).update(maximum_credits=2)
        with self.assertRaises(s.RegistrationConflict):
            w.register_course(actor=self.root,term_id=row.pk,course_id=self.course.pk,registration_type='REGULAR',reason='Too many credits')
        self.assertFalse(m.StudentCourseRegistration.objects.exists())

    def test_course_capacity_and_duplicate_are_atomic(self):
        row=self.course_registration()
        with self.assertRaises(ValidationError):
            w.register_course(actor=self.root,term_id=row.term_registration_id,course_id=self.course.pk,registration_type='REGULAR',reason='Duplicate')
        self.assertEqual(m.StudentCourseRegistration.objects.count(),1)
        self.assertEqual(m.RegistrationEvent.objects.count(),m.RegistrationAudit.objects.count())

    def test_roster_requires_timetable_then_preserves_history(self):
        row=self.approved_course();today=timezone.localdate()
        with self.assertRaises(s.RegistrationConflict):
            w.assign_roster(actor=self.root,registration_id=row.pk,mapping_id=self.mapping.pk,expected_version=row.version,effective_date=today,reason='No timetable')
        with patch('apps.term_registration.integrations.require_timetable'):
            roster=w.assign_roster(actor=self.root,registration_id=row.pk,mapping_id=self.mapping.pk,expected_version=row.version,effective_date=today,reason='Assign')
        row.refresh_from_db()
        with patch('apps.term_registration.workflows.timezone.localdate',return_value=today+timedelta(days=1)):
            w.transition_registration(actor=self.root,pk=row.pk,expected_version=row.version,target='DROPPED',effective_date=today+timedelta(days=1),reason='Drop')
        from apps.term_registration.selectors import as_of_roster
        self.assertTrue(as_of_roster(m.CourseOfferingSectionStudent.objects.all(),today).exists())
        self.assertFalse(as_of_roster(m.CourseOfferingSectionStudent.objects.all(),today+timedelta(days=1)).exists())
        from apps.teaching_timetable.engine import roster as teaching_roster
        self.assertIn(self.enrolment.student_id,teaching_roster(self.mapping,today))

    def test_same_day_drop_rolls_back(self):
        row=self.approved_course();today=timezone.localdate()
        with patch('apps.term_registration.integrations.require_timetable'):
            w.assign_roster(actor=self.root,registration_id=row.pk,mapping_id=self.mapping.pk,expected_version=row.version,effective_date=today,reason='Assign')
        row.refresh_from_db()
        with self.assertRaises(s.RegistrationConflict):
            w.transition_registration(actor=self.root,pk=row.pk,expected_version=row.version,target='DROPPED',effective_date=today,reason='Invalid zero length')
        row.refresh_from_db();self.assertEqual(row.registration_status,'APPROVED')

    def test_event_delivery_is_retry_safe_and_rolls_back_failure(self):
        from apps.term_registration.integrations import deliver
        calls=[]
        def fail(*args): raise RuntimeError('unavailable')
        with self.assertRaises(RuntimeError): deliver('test',fail)
        self.assertFalse(m.EventDelivery.objects.exists())
        count=deliver('test',lambda *args:calls.append(args))
        self.assertGreater(count,0)
        self.assertEqual(deliver('test',lambda *args:calls.append(args)),0)

    def test_database_course_and_roster_ownership(self):
        row=self.course_registration()
        other=m.ProgrammeTermOffering.objects.create(academic_term=self.term,programme=self.programme,curriculum_scheme=self.scheme,semester=__import__('apps.academic_calendar.models',fromlist=['Semester']).Semester.objects.create(semester_number=2,semester_name='Second'),created_by=self.root,updated_by=self.root)
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.StudentCourseRegistration.objects.filter(pk=row.pk).update(programme_term_offering=other)
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.CourseOfferingSection.objects.filter(pk=self.mapping.pk).update(programme_term_offering=other)

    def test_outbox_failure_rolls_back_command(self):
        count=m.ClassSection.objects.count()
        with patch.object(m.RegistrationEvent.objects,'create',side_effect=RuntimeError('outbox failure')):
            with self.assertRaises(RuntimeError):
                w.save_group(actor=self.root,resource='sections',values={'programme_term_offering_id':self.offering.pk,'section_code':'C'},reason='Atomic')
        self.assertEqual(m.ClassSection.objects.count(),count)


    def test_future_drop_cannot_release_a_reserved_seat_early(self):
        row=self.approved_course()
        with self.assertRaises(ValidationError):
            w.transition_registration(actor=self.root,pk=row.pk,expected_version=row.version,target='DROPPED',effective_date=timezone.localdate()+timedelta(days=1),reason='Future drop')
        row.refresh_from_db()
        self.assertEqual(row.registration_status,'APPROVED')


    def test_course_can_complete_after_teaching_term_ends(self):
        row=self.approved_course()
        day=self.term.end_date+timedelta(days=1)
        with patch('apps.term_registration.workflows.timezone.localdate',return_value=day):
            row=w.transition_registration(actor=self.root,pk=row.pk,expected_version=row.version,target='COMPLETED',effective_date=day,reason='Results finalized')
        self.assertEqual(row.registration_status,'COMPLETED')


    def test_completed_courses_still_count_toward_term_credit_limit(self):
        row=self.approved_course()
        w.transition_registration(actor=self.root,pk=row.pk,expected_version=row.version,target='COMPLETED',effective_date=timezone.localdate(),reason='Completed')
        self.assertEqual(w.credits(row.term_registration),Decimal('3'))
