from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from . import test_registration as fixtures
from apps.term_registration import models as m
from apps.tenancy.models import InstitutionModule,Membership,ScopeGrant


@override_settings(ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True)
class ApiTests(TestCase):
    setUp=fixtures.RegistrationTests.setUp
    def client_for(self,user):
        client=APIClient();client.force_authenticate(user);return client
    def staff(self,limits=None):
        user=get_user_model().objects.create_user(username='registrar')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='term_registration',codename__in=['manage_registration','view_registration']))
        InstitutionModule.objects.filter(institution=self.institution).update(term_registration=True)
        membership=Membership.objects.create(user=user,institution=self.institution)
        self.grant=ScopeGrant.objects.create(membership=membership,role='INSTITUTION_ADMIN',record_limits=limits or {})
        return user
    def draft_data(self):
        return {'offering_id':self.offering.pk,'enrolment_id':self.enrolment.pk}
    def test_command_retry_and_no_store(self):
        client=self.client_for(self.root);url='/api/v1/registration/commands/create-draft/'
        first=client.post(url,self.draft_data(),format='json',HTTP_IDEMPOTENCY_KEY='retry')
        self.assertEqual(first.status_code,200,first.data)
        self.assertEqual(first.data,client.post(url,self.draft_data(),format='json',HTTP_IDEMPOTENCY_KEY='retry').data)
        self.assertEqual(first['Cache-Control'],'private, no-store')
        self.assertEqual(m.StudentTermRegistration.objects.count(),1)
    def test_unknown_fields_and_disabled_module(self):
        client=self.client_for(self.root)
        response=client.post('/api/v1/registration/commands/create-draft/',{**self.draft_data(),'registration_status':'APPROVED'},format='json',HTTP_IDEMPOTENCY_KEY='forged')
        self.assertEqual(response.status_code,400)
        with override_settings(TERM_REGISTRATION_ENABLED=False):
            self.assertEqual(client.get('/api/v1/registration/offerings/').status_code,403)
    def test_scope_and_replay_reauthorize(self):
        user=self.staff();client=self.client_for(user)
        self.assertEqual(client.get('/api/v1/registration/offerings/').data['count'],1)
        url='/api/v1/registration/commands/create-draft/'
        self.assertEqual(client.post(url,self.draft_data(),format='json',HTTP_IDEMPOTENCY_KEY='scoped').status_code,200)
        self.grant.is_active=False;self.grant.save()
        self.assertEqual(client.post(url,self.draft_data(),format='json',HTTP_IDEMPOTENCY_KEY='scoped').status_code,404)
        self.assertEqual(client.get('/api/v1/registration/offerings/').data['count'],0)
    def test_student_and_record_limits(self):
        user=self.staff({'students':[],'registration-sections':[]});client=self.client_for(user)
        response=client.post('/api/v1/registration/commands/create-draft/',self.draft_data(),format='json',HTTP_IDEMPOTENCY_KEY='restricted')
        self.assertEqual(response.status_code,404,response.data)
        self.assertEqual(client.get('/api/v1/registration/sections/').data['count'],0)
        self.assertEqual(client.get('/api/v1/registration/lookups/enrolments/?programme_id='+str(self.programme.pk)).data['count'],0)
    def test_cross_institution_identifiers(self):
        from apps.organization.models import Institution,Campus,Department,Programme
        from apps.curriculum_catalog.models import CurriculumScheme
        user=self.staff();client=self.client_for(user)
        institution=Institution.objects.create(university=self.institution.university,institution_code='OTHER',institution_name='Other')
        campus=Campus.objects.create(institution=institution,campus_code='O',campus_name='Other')
        department=Department.objects.create(campus=campus,department_code='O',department_name='Other')
        programme=Programme.objects.create(department=department,programme_code='O',programme_name='Other',programme_level='UG',duration_semesters=6)
        scheme=CurriculumScheme.objects.create(programme=programme,scheme_code='OTHER',scheme_name='Other',regulation_year=2026,effective_from=self.scheme.effective_from,status='ACTIVE')
        foreign=m.ProgrammeTermOffering.objects.create(programme=programme,curriculum_scheme=scheme,academic_term=self.term,semester=self.semester,created_by=self.root,updated_by=self.root)
        self.assertEqual(client.get('/api/v1/registration/offerings/').data['count'],1)
        self.assertEqual(client.get(f'/api/v1/registration/offerings/{foreign.pk}/').status_code,404)
        response=client.post('/api/v1/registration/commands/create-draft/',{**self.draft_data(),'offering_id':foreign.pk},format='json',HTTP_IDEMPOTENCY_KEY='foreign')
        self.assertEqual(response.status_code,404,response.data)
    def test_personal_requires_verified_link(self):
        from apps.people_master.models import AccountLink
        user=get_user_model().objects.create_user(username='student')
        client=self.client_for(user)
        self.assertEqual(client.get('/api/v1/registration/mine/').status_code,404)
        InstitutionModule.objects.filter(institution=self.institution).update(term_registration=True)
        Membership.objects.create(user=user,institution=self.institution)
        AccountLink.objects.create(user=user,student=self.enrolment.student)
        from apps.term_registration.services import create_draft
        create_draft(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk)
        self.assertEqual(client.get('/api/v1/registration/mine/?student_id=999').data['count'],1)
        self.assertEqual(client.get('/api/v1/registration/terms/').status_code,403)
    def test_bulk_preview_and_import_parse(self):
        client=self.client_for(self.root)
        response=client.post('/api/v1/registration/bulk/',{'rows':[{'operation':'create-draft','data':self.draft_data()}],'dry_run':True},format='json',HTTP_IDEMPOTENCY_KEY='preview')
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(m.StudentTermRegistration.objects.exists())
        response=client.post('/api/v1/registration/import/parse/',{'content':'bad,header\n1,2'},format='json')
        self.assertEqual(response.status_code,400)
