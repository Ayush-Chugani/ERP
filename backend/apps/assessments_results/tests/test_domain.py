from datetime import date
from decimal import Decimal as D
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError,transaction
from rest_framework.exceptions import ValidationError,PermissionDenied
from rest_framework.test import APIClient
from apps.teaching_timetable.tests import test_services as fixtures
from apps.term_registration import models as reg
from apps.assessments_results import models as m,services as s,validators as v
from apps.assessments_results.api.commands import execute
RULES={'internal_weight':'100','external_weight':'0','minimum_internal':'0','minimum_external':'0','best_n':1,'aggregation':'MEAN','special':{'ABSENT':'ZERO','EXEMPTED':'EXCLUDE','MALPRACTICE':'BLOCK'},'rounding':'HALF_UP','repeat':'LATEST','gpa_statuses':['PASS','FAIL','ABSENT'],'credit_statuses':['PASS'],'max_grade_point':'10','grace':'0','event_maximum':'EQUAL_COMPONENT','failure_grade':'F','show_marks':False}
BANDS=[{'grade_letter':'F','grade_point':D('0'),'minimum_percentage':D('0'),'maximum_percentage':D('50'),'result_status':'FAIL'},{'grade_letter':'P','grade_point':D('10'),'minimum_percentage':D('50'),'maximum_percentage':D('100'),'result_status':'PASS'}]
@override_settings(ASSESSMENTS_RESULTS_ENABLED=True,ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class AssessmentTests(TestCase):
    def setUp(self):
        fixtures.TimetableTests.setUp(self)
        self.course.credits=D('3');self.course.save()
        self.reviewer=get_user_model().objects.create_superuser(username='m10-reviewer',password='not-used')
        self.termreg=reg.StudentTermRegistration.objects.create(enrolment=self.enrolment,programme=self.programme,programme_term_offering=self.offering,class_section=self.section,registration_date=date(2026,9,1),registration_status='APPROVED',created_by=self.root,updated_by=self.root)
        self.registration=reg.StudentCourseRegistration.objects.create(term_registration=self.termreg,programme_term_offering=self.offering,course_offering=self.course_offering,registration_date=date(2026,9,1),registration_status='APPROVED',created_by=self.root,updated_by=self.root)
        self.scale=s.configure_scale(actor=self.root,institution_id=self.institution.pk,values={'scale_name':'TEST ONLY','effective_from':date(2026,1,1)},rules=BANDS,reason='Test grade bands')
        self.policy=s.configure_policy(actor=self.root,offering_id=self.course_offering.pk,grade_scale_id=self.scale.pk,expected_number=0,rules=RULES,reason='Test policy')
        self.component=s.component(actor=self.root,offering_id=self.course_offering.pk,values={'component_code':'TEST','component_name':'Test','component_type':'QUIZ','maximum_marks':D('100'),'weightage_percent':D('100'),'is_mandatory':True},reason='Test component')
        self.event=s.create_event(actor=self.root,component_id=self.component.pk,policy_id=self.policy.pk,values={'event_title':'Test event','assessment_date':date(2026,9,7),'maximum_marks':D('100'),'attempt_number':1},reason='Test event')
    def transition(self,action,actor=None):
        self.event.refresh_from_db();self.event=s.transition_event(actor=actor or self.root,pk=self.event.pk,expected_version=self.event.version,action=action,reason='Test '+action)
    def marks(self,value=D('80')):
        self.event.refresh_from_db();self.event=s.mark(actor=self.root,event_id=self.event.pk,expected_version=self.event.version,entries=[{'course_registration_id':self.registration.pk,'attendance_status':'PRESENT','marks_obtained':value}],reason='Test mark')
    def published_event(self):self.transition('conduct');self.marks();self.transition('publish',self.reviewer)
    def calculate(self,expected=0):return s.calculate_course(actor=self.root,registration_id=self.registration.pk,attempt=1,policy_id=self.policy.pk,external_percentage=D('0'),expected_version=expected,reason='Test calculation')
    def test_complete_course_and_term_publication(self):
        self.published_event();result=self.calculate();self.assertEqual(result.total_marks,D('80'))
        with self.assertRaises(PermissionDenied):s.transition_result(actor=self.root,resource='course',pk=result.pk,expected_version=result.version,action='publish',reason='Own review')
        s.transition_result(actor=self.reviewer,resource='course',pk=result.pk,expected_version=result.version,action='publish',reason='Reviewed')
        term=s.calculate_term(actor=self.root,term_registration_id=self.termreg.pk,expected_version=0,reason='Term calculation')
        self.assertEqual(term.sgpa,D('10'));self.assertEqual(term.credits_earned,D('3'))
        s.transition_result(actor=self.reviewer,resource='term',pk=term.pk,expected_version=term.version,action='publish',reason='Term review')
        self.assertEqual(m.Publication.objects.count(),3)
    def test_atomic_marks_and_stale(self):
        self.transition('conduct');version=self.event.version
        with self.assertRaises(ValidationError):s.mark(actor=self.root,event_id=self.event.pk,expected_version=version,entries=[{'course_registration_id':self.registration.pk,'attendance_status':'PRESENT','marks_obtained':D('80')},{'course_registration_id':self.registration.pk,'attendance_status':'PRESENT','marks_obtained':D('101')}],reason='Invalid batch')
        self.assertFalse(m.StudentAssessmentMark.objects.exists());self.marks()
        with self.assertRaises(s.Conflict):s.mark(actor=self.root,event_id=self.event.pk,expected_version=version,entries=[{'course_registration_id':self.registration.pk,'attendance_status':'ABSENT'}],reason='Stale')
    def test_missing_marks_and_self_publication(self):
        self.transition('conduct')
        with self.assertRaises(s.Conflict):self.transition('publish',self.reviewer)
        self.marks()
        with self.assertRaises(PermissionDenied):self.transition('publish')
    def test_stale_calculation_after_mark_correction(self):
        self.published_event();result=self.calculate();self.transition('reopen',self.reviewer);self.marks(D('90'));self.transition('publish',self.reviewer)
        with self.assertRaises(s.Conflict):s.transition_result(actor=self.reviewer,resource='course',pk=result.pk,expected_version=result.version,action='publish',reason='Stale calculation')
    def test_idempotency_and_disabled_api(self):
        data={'pk':self.event.pk,'expected_version':self.event.version,'action':'conduct','reason':'API'}
        a=execute(actor=self.root,operation='transition-event',data=data,key='same');self.assertEqual(a,execute(actor=self.root,operation='transition-event',data=data,key='same'))
        with self.assertRaises(s.Conflict):execute(actor=self.root,operation='transition-event',data={**data,'reason':'Changed'},key='same')
        client=APIClient();client.force_authenticate(self.root)
        with override_settings(ASSESSMENTS_RESULTS_ENABLED=False):self.assertEqual(client.get('/api/v1/assessments/events/').status_code,403)
    def test_student_visibility_and_withholding(self):
        from apps.people_master.models import AccountLink
        from apps.tenancy.models import Membership,InstitutionModule
        student=get_user_model().objects.create_user(username='m10-student');AccountLink.objects.create(user=student,student=self.enrolment.student);Membership.objects.create(user=student,institution=self.institution);InstitutionModule.objects.filter(institution=self.institution).update(assessments_results=True)
        client=APIClient();client.force_authenticate(student)
        self.published_event();result=self.calculate();self.assertEqual(client.get('/api/v1/assessments/mine/').data['results'],[])
        result=s.transition_result(actor=self.reviewer,resource='course',pk=result.pk,expected_version=result.version,action='publish',reason='Reviewed')
        data=client.get('/api/v1/assessments/mine/').data['results'];self.assertEqual(len(data),1);self.assertNotIn('remarks',data[0]);self.assertNotIn('evidence',data[0]);self.assertNotIn('total_marks',data[0])
        result=s.transition_result(actor=self.root,resource='course',pk=result.pk,expected_version=result.version,action='reopen',reason='Correct')
        self.assertEqual(len(client.get('/api/v1/assessments/mine/').data['results']),1)
        s.transition_result(actor=self.root,resource='course',pk=result.pk,expected_version=result.version,action='withhold',reason='Hold')
        self.assertEqual(client.get('/api/v1/assessments/mine/').data['results'][0]['result_status'],'WITHHELD')
        self.assertEqual(client.get('/api/v1/assessments/events/').status_code,403)
    def test_database_ownership(self):
        from apps.curriculum_catalog.models import CourseCatalog
        course=CourseCatalog.objects.create(owning_department=self.department,course_category=self.course.course_category,course_code='M10B',course_title='Other course',course_type='THEORY')
        other=reg.CourseOffering.objects.create(programme_term_offering=self.offering,course=course,offering_code='Other',status='ACTIVE',created_by=self.root,updated_by=self.root)
        with self.assertRaises(IntegrityError),transaction.atomic():m.AssessmentEvent.objects.filter(pk=self.event.pk).update(course_offering_id=other.pk)

    def test_teacher_roster_and_scope_revocation(self):
        from django.contrib.auth.models import Permission
        from apps.people_master.models import AccountLink
        from apps.tenancy.models import Membership,InstitutionModule,ScopeGrant
        from apps.assessments_results import selectors as q
        teacher=get_user_model().objects.create_user(username='m10-teacher');AccountLink.objects.create(user=teacher,employee=self.employee)
        teacher.user_permissions.add(*Permission.objects.filter(content_type__app_label='assessments_results',codename__in=['view_assessment','mark_assessment']))
        InstitutionModule.objects.filter(institution=self.institution).update(assessments_results=True)
        member=Membership.objects.create(user=teacher,institution=self.institution);grant=ScopeGrant.objects.create(membership=member,role='TEACHER')
        self.transition('conduct')
        self.assertEqual(q.roster(teacher,self.event.pk)['rows'],[])
        reg.CourseOfferingSectionStudent.objects.create(course_registration=self.registration,course_offering=self.course_offering,course_offering_section=self.mapping,session_type='LECTURE',effective_from=date(2026,9,1),created_by=self.root,updated_by=self.root)
        self.assertEqual(len(q.roster(teacher,self.event.pk)['rows']),1)
        grant.is_active=False;grant.save()
        from rest_framework.exceptions import NotFound
        with self.assertRaises(NotFound):q.roster(teacher,self.event.pk)
    def test_audit_failure_rolls_back_marks(self):
        from unittest.mock import patch
        self.transition('conduct')
        with patch.object(m.Audit.objects,'create',side_effect=RuntimeError('Injected')):
            with self.assertRaises(RuntimeError):self.marks()
        self.assertFalse(m.StudentAssessmentMark.objects.exists())
    def test_withheld_reopening_does_not_release(self):
        self.published_event();result=self.calculate()
        result=s.transition_result(actor=self.reviewer,resource='course',pk=result.pk,expected_version=result.version,action='publish',reason='Reviewed')
        result=s.transition_result(actor=self.root,resource='course',pk=result.pk,expected_version=result.version,action='withhold',reason='Held')
        result=s.transition_result(actor=self.root,resource='course',pk=result.pk,expected_version=result.version,action='reopen',reason='Correction')
        self.assertTrue(result.is_withheld)

    def test_failed_bulk_publication_rolls_back_every_result(self):
        from apps.assessments_results.api.commands import execute_batch
        self.published_event();result=self.calculate()
        row={'operation':'transition-result','data':{'resource':'course','pk':result.pk,'expected_version':result.version,'action':'publish','reason':'Bulk review'}}
        with self.assertRaises(ValidationError):execute_batch(actor=self.reviewer,rows=[row,{'operation':'transition-result','data':{**row['data'],'pk':99999999}}],key='bulk')
        result.refresh_from_db();self.assertEqual(result.state,'CALCULATED')
        self.assertFalse(m.Publication.objects.filter(resource='studentcourseresult').exists())

    def test_workspace_reads_and_health(self):
        from django.core.management import call_command
        from io import StringIO
        client=APIClient();client.force_authenticate(self.root)
        for name in ['offerings','components','events','policies','scales','grades','registrations','terms','course-results','term-results','audit']:
            response=client.get('/api/v1/assessments/'+name+'/')
            self.assertEqual(response.status_code,200,(name,response.data))
            self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(client.get('/api/v1/assessments/reports/grade-distribution/').status_code,200)
        output=StringIO();call_command('assessment_health',actor=self.root.pk,stdout=output)
        self.assertIn('unpublished_events',output.getvalue())
