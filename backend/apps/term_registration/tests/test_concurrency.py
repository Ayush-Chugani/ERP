from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase, override_settings
from django.db import close_old_connections, connections
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import test_registration as fixtures
from apps.term_registration import models as m, services as s, workflows as w


@override_settings(ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True)
class ConcurrencyTests(TransactionTestCase):
    setUp=fixtures.RegistrationTests.setUp
    def second_enrolment(self):
        from apps.admission_enrolment import models as a
        from apps.people_master.models import Student
        student=Student.objects.create(student_number='M7RACE',institution=self.institution,first_name='Second',display_name='Second',student_status='ACTIVE')
        applicant=a.AdmissionApplicant.objects.create(institution=self.institution,first_name='Second',display_name='Second',created_by=self.root,updated_by=self.root)
        app=a.AdmissionApplication.objects.create(application_number='M7RACE',admission_applicant=applicant,admitted_student=student,programme=self.programme,academic_year=self.year,application_date=timezone.localdate(),application_status='ADMITTED',eligibility_status='ELIGIBLE',created_by=self.root,updated_by=self.root)
        return a.StudentProgrammeEnrolment.objects.create(application=app,student=student,programme=self.programme,curriculum_scheme=self.scheme,admission_academic_year=self.year,admission_semester=self.semester,admission_date=timezone.localdate(),created_by=self.root,updated_by=self.root)
    def race(self,functions):
        barrier=Barrier(2)
        def run(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=10);fn();return 'success'
            except (s.RegistrationConflict,ValidationError): return 'conflict'
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run,fn) for fn in functions]
            return [future.result(timeout=30) for future in futures]
    def drafts(self):
        result=[]
        for enrolment in (self.enrolment,self.second_enrolment()):
            row=s.create_draft(actor=self.root,enrolment_id=enrolment.pk,offering_id=self.offering.pk,section_id=self.section.pk)
            s.approve_progression(actor=self.root,enrolment_id=enrolment.pk,offering_id=self.offering.pk,enrolment_version=enrolment.version,offering_version=1,reason='Approved')
            result.append(row)
        return result
    def test_last_section_seat(self):
        rows=self.drafts()
        results=self.race([lambda row=row:s.transition_term(actor=self.root,registration_id=row.pk,expected_version=1,target='REGISTERED',reason='Last seat') for row in rows])
        self.assertCountEqual(results,['success','conflict'])
        self.assertEqual(m.StudentTermRegistration.objects.filter(registration_status='REGISTERED').count(),1)
    def test_duplicate_registration(self):
        fn=lambda:s.create_draft(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk)
        self.assertCountEqual(self.race([fn,fn]),['success','conflict'])
        self.assertEqual(m.StudentTermRegistration.objects.count(),1)
    def test_competing_class_transfers(self):
        m.ClassSection.objects.filter(pk=self.section.pk).update(capacity=2)
        rows=self.drafts()
        for row in rows:
            s.transition_term(actor=self.root,registration_id=row.pk,expected_version=1,target='REGISTERED',reason='Register')
        destination=w.save_group(actor=self.root,resource='sections',values={'programme_term_offering_id':self.offering.pk,'section_code':'B','capacity':1},reason='Destination')
        results=self.race([lambda row=row:w.allocate(actor=self.root,pk=row.pk,expected_version=2,section_id=destination.pk,reason='Transfer') for row in rows])
        self.assertCountEqual(results,['success','conflict'])
        self.assertEqual(m.StudentTermRegistration.objects.filter(class_section=destination).count(),1)
