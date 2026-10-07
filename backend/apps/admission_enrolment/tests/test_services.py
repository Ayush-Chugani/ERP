from datetime import date
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework.exceptions import PermissionDenied
from apps.people_master.tests.test_services import fixture, student, address
from apps.people_master.services import execute, Command, set_primary, version
from apps.people_master.models import Student, StudentAddress
from apps.organization.models import Programme
from apps.academic_calendar.models import AcademicYear, Semester
from apps.curriculum_catalog.models import CurriculumScheme
from apps.admission_enrolment import models as m, services as s


@override_settings(ADMISSION_ENROLMENT_ENABLED=True, PEOPLE_MASTER_ENABLED=True)
class AdmissionTests(TestCase):
    def setUp(self):
        fixture(self)
        self.programme = Programme.objects.create(department=self.department,programme_code='M6P',programme_name='Programme',programme_level='UG',duration_semesters=6)
        self.year = AcademicYear.objects.create(year_code='2026-27',start_date=date(2026,1,1),end_date=date(2026,12,31),status='ACTIVE')
        self.semester = Semester.objects.create(semester_number=1,semester_name='First')
        self.scheme = CurriculumScheme.objects.create(programme=self.programme,scheme_code='M6S',scheme_name='Scheme',regulation_year=2026,effective_from=date(2026,1,1),status='ACTIVE')
        self.person = student(self)
        row=address(self,self.person)
        set_primary(StudentAddress,row.pk,actor=self.root,expected_version=version(row),reason='Current')
        self.person=execute(Command(Student,self.root,{'status':'ACTIVE'},self.person.pk,'status',version(self.person),'Activate'))
        self.applicant=s.save_record(actor=self.root,model=m.AdmissionApplicant,values={'institution_id':self.institution.pk,'first_name':'Applicant','display_name':'Applicant'})
        self.application=s.save_record(actor=self.root,model=m.AdmissionApplication,values={'admission_applicant_id':self.applicant.pk,'programme_id':self.programme.pk,'academic_year_id':self.year.pk,'application_date':date(2026,1,2)})
        for target in ['SUBMITTED','UNDER_REVIEW','ELIGIBLE','SELECTED']:
            self.application=s.transition_application(actor=self.root,pk=self.application.pk,version=self.application.version,target=target,reason='Reviewed evidence')
        self.payload={'student_id':self.person.pk,'curriculum_scheme_id':self.scheme.pk,'admission_semester_id':self.semester.pk,'admission_date':'2026-02-01'}

    def clearance(self):
        return s.record_clearance(actor=self.root,pk=self.application.pk,version=self.application.version,reference='MANUAL-001')

    def admit(self,key='test-key'):
        return s.admit_application(actor=self.root,application_id=self.application.pk,version=self.application.version,payload=self.payload,idempotency_key=key)

    def test_clearance_required_and_retry(self):
        with self.assertRaises(s.Conflict):
            self.admit()
        self.clearance()
        row=self.admit()
        self.assertEqual(self.admit().pk,row.pk)
        self.assertEqual(m.StudentProgrammeEnrolment.objects.count(),1)
        self.assertEqual(m.EnrolmentStatusHistory.objects.count(),1)
        self.payload['admission_date']='2026-02-02'
        with self.assertRaises(s.Conflict):
            self.admit()

    def test_failure_rolls_back_entire_conversion(self):
        self.clearance()
        count=m.AdmissionAudit.objects.count()
        with patch.object(s,'history',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.admit()
        self.application.refresh_from_db(); self.applicant.refresh_from_db()
        self.assertEqual(self.application.application_status,'SELECTED')
        self.assertIsNone(self.applicant.canonical_student_id)
        self.assertFalse(m.StudentProgrammeEnrolment.objects.exists())
        self.assertEqual(m.AdmissionAudit.objects.count(),count)

    def test_history_append_only_and_stale_lifecycle(self):
        self.clearance(); row=self.admit()
        row=s.transition_enrolment(actor=self.root,pk=row.pk,version=row.version,target='ON_BREAK',reason='Approved break',effective_date=date(2026,3,1))
        self.assertEqual(row.enrolment_status,'ON_BREAK')
        with self.assertRaises(s.Conflict):
            s.transition_enrolment(actor=self.root,pk=row.pk,version=1,target='ACTIVE',reason='Resume',effective_date=date(2026,4,1))
        with self.assertRaises(ModelValidationError):
            m.EnrolmentStatusHistory.objects.all().update(reason='rewrite')

    def test_wrong_scheme_programme_database_defense(self):
        self.clearance(); row=self.admit()
        other=Programme.objects.create(department=self.department,programme_code='OTHER',programme_name='Other',programme_level='UG',duration_semesters=6)
        scheme=CurriculumScheme.objects.create(programme=other,scheme_code='OTHER',scheme_name='Other',regulation_year=2026,effective_from=date(2026,1,1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.StudentProgrammeEnrolment.objects.filter(pk=row.pk).update(curriculum_scheme=scheme)

    def test_api_clearance_admission_and_no_delete(self):
        from rest_framework.test import APIClient
        client=APIClient(); client.force_authenticate(self.root)
        base=f'/api/v1/admissions/applications/{self.application.pk}/'
        response=client.post(base+'fee-clearance/',{'reference':'ADMIN-2'},format='json',HTTP_IF_MATCH=str(self.application.version))
        self.assertEqual(response.status_code,201,response.data)
        response=client.post(base+'admit/',self.payload,format='json',HTTP_IF_MATCH=str(self.application.version),HTTP_IDEMPOTENCY_KEY='api-key')
        self.assertEqual(response.status_code,200,response.data)
        self.assertIsInstance(response.data['enrolment_id'],str)
        self.assertEqual(client.delete(base).status_code,405)

    def test_mass_assignment_and_missing_foreign_key(self):
        from rest_framework.test import APIClient
        client=APIClient(); client.force_authenticate(self.root)
        response=client.post('/api/v1/admissions/applicants/',{'institution_id':self.institution.pk,'first_name':'Name','display_name':'Name','canonical_student_id':self.person.pk},format='json')
        self.assertEqual(response.status_code,400)
        response=client.post('/api/v1/admissions/applicants/',{'institution_id':65000,'first_name':'Name','display_name':'Name'},format='json')
        self.assertEqual(response.status_code,400)

    def test_authenticated_unprivileged_cannot_read_or_clear(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        actor=get_user_model().objects.create_user(username='reader',password='test-pass')
        client=APIClient(); client.force_authenticate(actor)
        self.assertEqual(client.get('/api/v1/admissions/applicants/').status_code,403)
        with self.assertRaises(PermissionDenied):
            s.record_clearance(actor=actor,pk=self.application.pk,version=self.application.version,reference='Unauthorized')

    @override_settings(ADMISSION_ENROLMENT_ENABLED=False)
    def test_module_disabled(self):
        with self.assertRaises(PermissionDenied):
            self.clearance()
