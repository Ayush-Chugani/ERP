from datetime import date
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.utils import timezone
from apps.admission_enrolment.tests import test_services as admission_fixtures
from apps.admission_enrolment import services as admission
from apps.academic_calendar.models import AcademicTerm
from apps.term_registration import models as m, services as s


@override_settings(ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True)
class RegistrationTests(TestCase):
    def setUp(self):
        admission_fixtures.AdmissionTests.setUp(self)
        admission.record_clearance(actor=self.root,pk=self.application.pk,version=self.application.version,reference='M7')
        self.enrolment=admission.admit_application(actor=self.root,application_id=self.application.pk,version=self.application.version,payload=self.payload,idempotency_key='m7-fixture')
        today=timezone.localdate()
        self.term=AcademicTerm.objects.create(academic_year=self.year,term_code='M7',term_name='M7 Term',term_type='ODD',start_date=date(today.year,1,1),end_date=date(today.year,12,31),registration_start_date=date(today.year,1,1),registration_end_date=date(today.year,12,31),status='REGISTRATION_OPEN')
        self.offering=m.ProgrammeTermOffering.objects.create(academic_term=self.term,programme=self.programme,curriculum_scheme=self.scheme,semester=self.semester,status='REGISTRATION_OPEN',created_by=self.root,updated_by=self.root)
        self.section=m.ClassSection.objects.create(programme_term_offering=self.offering,section_code='A',capacity=1,created_by=self.root,updated_by=self.root)

    def draft(self):
        return s.create_draft(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk,section_id=self.section.pk)

    def approve(self):
        return s.approve_progression(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk,offering_version=self.offering.version,enrolment_version=self.enrolment.version,reason='Registrar checked progression evidence')

    def register(self,row):
        return s.transition_term(actor=self.root,registration_id=row.pk,expected_version=row.version,target='REGISTERED',reason='Register')

    def test_registrar_approval_required_and_draft_does_not_reserve(self):
        row=self.draft()
        self.assertEqual(m.StudentTermRegistration.objects.filter(registration_status__in=['REGISTERED','APPROVED']).count(),0)
        with self.assertRaises(s.RegistrationConflict):
            self.register(row)
        self.approve()
        row=self.register(row)
        self.assertEqual(row.registration_status,'REGISTERED')
        self.assertTrue(row.roll_number)
        self.assertEqual(m.RegistrationAudit.objects.count(),3)

    def test_progression_evidence_is_append_only(self):
        approval=self.approve()
        with self.assertRaises(ValidationError):
            approval.reason='Rewrite';approval.save()
        with self.assertRaises(ValidationError):
            m.ProgressionApproval.objects.all().delete()

    def test_changed_enrolment_invalidates_approval(self):
        row=self.draft();self.approve()
        self.enrolment.version+=1;self.enrolment.save()
        with self.assertRaises(s.RegistrationConflict):
            self.register(row)

    def test_capacity_is_checked_when_draft_registers(self):
        row=self.draft();self.approve()
        from apps.admission_enrolment import models as a
        from apps.people_master.models import Student
        person=Student.objects.create(student_number='M7SECOND',institution=self.institution,first_name='Second',display_name='Second Student',student_status='ACTIVE')
        applicant=a.AdmissionApplicant.objects.create(institution=self.institution,first_name='Second',display_name='Second Student',created_by=self.root,updated_by=self.root)
        app=a.AdmissionApplication.objects.create(application_number='M7SECOND',admission_applicant=applicant,admitted_student=person,programme=self.programme,academic_year=self.year,application_date=date(2026,1,1),application_status='ADMITTED',eligibility_status='ELIGIBLE',created_by=self.root,updated_by=self.root)
        enrolment=a.StudentProgrammeEnrolment.objects.create(application=app,student=person,programme=self.programme,curriculum_scheme=self.scheme,admission_academic_year=self.year,admission_semester=self.semester,admission_date=date(2026,2,1),created_by=self.root,updated_by=self.root)
        m.StudentTermRegistration.objects.create(enrolment=enrolment,programme=self.programme,programme_term_offering=self.offering,class_section=self.section,registration_date=timezone.localdate(),registration_status='REGISTERED',created_by=self.root,updated_by=self.root)
        with self.assertRaises(s.RegistrationConflict):
            self.register(row)
        row.refresh_from_db()
        self.assertEqual(row.registration_status,'DRAFT')

    def test_database_rejects_zero_capacity(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.ClassSection.objects.filter(pk=self.section.pk).update(capacity=0)

    def test_database_rejects_cross_programme_owner(self):
        from apps.organization.models import Programme
        other=Programme.objects.create(department=self.department,programme_code='M7OTHER',programme_name='Other',programme_level='UG',duration_semesters=6)
        row=self.draft()
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.StudentTermRegistration.objects.filter(pk=row.pk).update(programme=other)
