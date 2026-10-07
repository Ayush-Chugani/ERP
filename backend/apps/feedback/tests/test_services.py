from datetime import timedelta
from decimal import Decimal
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.teaching_timetable.tests import test_services as fixtures
from apps.feedback import models as m,services as s
@override_settings(FEEDBACK_ENABLED=True,FEEDBACK_PRIVACY_KEY='test-only-feedback-key-000000000000000000',ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class FeedbackTests(TestCase):
    def setUp(self):
        fixtures.TimetableTests.setUp(self)
        category=s.write_bank(actor=self.root,resource='categories',institution_id=self.institution.pk,values={'category_code':'FB','category_name':'Feedback'},reason='Test bank')
        self.questions=[]
        for kind in ['SINGLE_CHOICE','MULTIPLE_CHOICE','RATING','TEXT']:
            values={'feedback_category_id':category.pk,'question_text':kind,'response_type':kind}
            if kind=='RATING':values.update(rating_min=Decimal('1'),rating_max=Decimal('5'),rating_step=Decimal('1'))
            if kind=='TEXT':values['text_limit']=200
            question=s.write_bank(actor=self.root,resource='questions',institution_id=self.institution.pk,values=values,reason='Test question');self.questions.append(question)
            if 'CHOICE' in kind:
                for n in [1,2]:s.write_bank(actor=self.root,resource='choices',institution_id=self.institution.pk,values={'feedback_question_id':question.pk,'choice_text':str(n),'score':Decimal(n),'display_order':n},reason='Test choice')
        self.questionnaire=s.write_bank(actor=self.root,resource='questionnaires',institution_id=self.institution.pk,values={'questionnaire_code':'FB','questionnaire_name':'Feedback','questionnaire_type':'COURSE','is_anonymous':True},reason='Test template')
        self.questionnaire=s.replace_items(actor=self.root,pk=self.questionnaire.pk,expected_version=self.questionnaire.version,items=[{'question_id':q.pk,'display_order':i+1,'is_required':True} for i,q in enumerate(self.questions)],reason='Test items')
    def activate(self):
        self.questionnaire=s.questionnaire_action(actor=self.root,pk=self.questionnaire.pk,expected_version=self.questionnaire.version,action='activate',reason='Ready')
    def cycle(self):
        self.activate();now=timezone.now()
        self.cycle_obj=s.create_cycle(actor=self.root,questionnaire_id=self.questionnaire.pk,values={'academic_term_id':self.term.pk,'cycle_name':'Test','start_at':now-timedelta(hours=1),'end_at':now+timedelta(hours=1),'result_visibility':'PUBLIC','minimum_cohort':2,'allow_text_review':False,'target_policy':'ENROLLED'},reason='Schedule')
        self.cycle_obj=s.cycle_action(actor=self.root,pk=self.cycle_obj.pk,expected_version=self.cycle_obj.version,action='open',reason='Open');return self.cycle_obj
    def test_activate_freeze_clone(self):
        self.activate()
        with self.assertRaises(s.Conflict):s.replace_items(actor=self.root,pk=self.questionnaire.pk,expected_version=self.questionnaire.version,items=[{'question_id':self.questions[0].pk,'display_order':1,'is_required':True}],reason='Change frozen')
        clone=s.questionnaire_action(actor=self.root,pk=self.questionnaire.pk,expected_version=self.questionnaire.version,action='clone',code='FB2',name='Next',reason='Clone')
        self.assertEqual(clone.status,'DRAFT');self.assertEqual(m.QuestionnaireItem.objects.filter(questionnaire=clone).count(),4)
    def test_choice_owner_and_text_choices(self):
        with self.assertRaises(ValidationError):s.write_bank(actor=self.root,resource='choices',institution_id=self.institution.pk,values={'feedback_question_id':self.questions[-1].pk,'choice_text':'Wrong'},reason='Invalid')
    def test_cycle_lifecycle_and_frozen_content(self):
        obj=self.cycle();self.assertEqual(len(obj.frozen['items']),4)
        s.write_bank(actor=self.root,resource='questions',institution_id=self.institution.pk,pk=self.questions[0].pk,expected_version=self.questions[0].version,values={'is_active':False},reason='Retire bank question')
        obj.refresh_from_db();self.assertEqual(len(obj.frozen['items']),4)
        closed=s.cycle_action(actor=self.root,pk=obj.pk,expected_version=obj.version,action='close',reason='Close')
        with self.assertRaises(s.Conflict):s.cycle_action(actor=self.root,pk=obj.pk,expected_version=closed.version,action='open',reason='Reopen')
    def test_empty_or_duplicate_items_rejected(self):
        before=m.QuestionnaireItem.objects.count()
        with self.assertRaises(ValidationError):s.replace_items(actor=self.root,pk=self.questionnaire.pk,expected_version=self.questionnaire.version,items=[{'question_id':self.questions[0].pk,'display_order':1,'is_required':True}]*2,reason='Duplicate')
        self.assertEqual(m.QuestionnaireItem.objects.count(),before)

    def student(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.people_master.models import AccountLink
        from apps.tenancy.models import Membership,InstitutionModule
        from apps.term_registration import models as r
        user=get_user_model().objects.create_user(username='feedback-student')
        user.user_permissions.add(Permission.objects.get(codename='submit_feedback',content_type__app_label='feedback'))
        AccountLink.objects.create(user=user,student=self.enrolment.student);Membership.objects.create(user=user,institution=self.institution)
        InstitutionModule.objects.filter(institution=self.institution).update(feedback=True)
        term=r.StudentTermRegistration.objects.create(enrolment=self.enrolment,programme_term_offering=self.offering,programme=self.programme,class_section=self.section,registration_status='APPROVED',registration_date=self.term.start_date,created_by=self.root,updated_by=self.root)
        self.registration=r.StudentCourseRegistration.objects.create(term_registration=term,course_offering=self.course_offering,programme_term_offering=self.offering,registration_status='APPROVED',registration_date=self.term.start_date,created_by=self.root,updated_by=self.root)
        return user
    def answers(self):
        answers={}
        for item in self.cycle_obj.frozen['items']:
            if item['response_type']=='SINGLE_CHOICE':value={'choice_id':item['choices'][0]['id']}
            elif item['response_type']=='MULTIPLE_CHOICE':value={'choice_ids':[c['id'] for c in item['choices']]}
            elif item['response_type']=='RATING':value={'numeric_score':'4'}
            else:value={'text_response':'<script>plain text</script>'}
            answers[item['id']]=value
        return answers
    def test_submission_atomic_private_and_retry_safe(self):
        self.cycle();user=self.student();target={'course_offering_id':self.course_offering.pk}
        first=s.submit(actor=user,cycle_id=self.cycle_obj.pk,target=target,answers=self.answers(),key='one')
        self.assertEqual(first,s.submit(actor=user,cycle_id=self.cycle_obj.pk,target=target,answers=self.answers(),key='one'))
        with self.assertRaises(s.Conflict):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target=target,answers=self.answers(),key='two')
        response=m.Response.objects.get();self.assertIsNone(response.term_registration_id)
        self.assertEqual(m.ResponseItem.objects.count(),4);self.assertEqual(m.ResponseItemChoice.objects.count(),2)
        self.assertNotEqual(first['receipt'],response.response_token)
        self.assertFalse(any(f.is_relation and f.related_model==m.Response for f in m.SubmissionLedger._meta.fields))
    def test_invalid_answers_leave_no_ledger_or_partial_response(self):
        self.cycle();user=self.student();answers=self.answers();answers['999999']={'text_response':'forged'}
        with self.assertRaises(ValidationError):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target={'course_offering_id':self.course_offering.pk},answers=answers,key='invalid')
        self.assertEqual(m.Response.objects.count(),0);self.assertEqual(m.SubmissionLedger.objects.count(),0)
    def test_closed_and_wrong_target_rejected(self):
        from rest_framework.exceptions import NotFound
        self.cycle();user=self.student()
        with self.assertRaises(NotFound):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target={'course_offering_id':999999},answers=self.answers(),key='wrong')
        s.cycle_action(actor=self.root,pk=self.cycle_obj.pk,expected_version=self.cycle_obj.version,action='close',reason='Close')
        with self.assertRaises(s.Conflict):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target={'course_offering_id':self.course_offering.pk},answers=self.answers(),key='late')
    def test_public_suppression_and_private_payloads(self):
        from rest_framework.test import APIClient
        self.cycle();user=self.student();client=APIClient();client.force_authenticate(user)
        available=client.get('/api/v1/feedback/available/');self.assertEqual(available.status_code,200)
        response=client.post(f'/api/v1/feedback/cycles/{self.cycle_obj.pk}/submit/',{'target':{'course_offering_id':self.course_offering.pk},'answers':self.answers()},format='json',HTTP_IDEMPOTENCY_KEY='api')
        self.assertEqual(response.status_code,200,response.data);self.assertEqual(response['Cache-Control'],'private, no-store')
        s.cycle_action(actor=self.root,pk=self.cycle_obj.pk,expected_version=self.cycle_obj.version,action='close',reason='Close')
        public=APIClient().get(f'/api/v1/feedback/public/cycles/{self.cycle_obj.pk}/results/?target=course:{self.course_offering.pk}')
        self.assertEqual(public.status_code,200,public.data);self.assertTrue(public.data['suppressed']);self.assertIsNone(public.data['response_count'])
        for key in ['student','term_registration','response_token','text_response']:self.assertNotIn(key,str(public.data))
    def test_partial_insert_failure_rolls_back_ledger(self):
        from unittest.mock import patch
        self.cycle();user=self.student()
        with patch.object(m.ResponseItemChoice.objects,'create',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target={'course_offering_id':self.course_offering.pk},answers=self.answers(),key='fail')
        self.assertEqual(m.Response.objects.count(),0);self.assertEqual(m.SubmissionLedger.objects.count(),0)

    def test_aggregate_correctness_and_query_budget(self):
        from apps.feedback import selectors as q
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.cycle();user=self.student();target={'course_offering_id':self.course_offering.pk}
        s.submit(actor=user,cycle_id=self.cycle_obj.pk,target=target,answers=self.answers(),key='sample')
        original=m.Response.objects.get();copy=m.Response.objects.create(feedback_cycle=self.cycle_obj,target_key=original.target_key,course_offering=self.course_offering)
        for row in list(m.ResponseItem.objects.filter(feedback_response=original)):
            new=m.ResponseItem.objects.create(feedback_response=copy,questionnaire_item_id=row.questionnaire_item_id,feedback_choice_id=row.feedback_choice_id,numeric_score=row.numeric_score,text_response=row.text_response)
            for selected in m.ResponseItemChoice.objects.filter(feedback_response_item=row):m.ResponseItemChoice.objects.create(feedback_response_item=new,feedback_choice_id=selected.feedback_choice_id)
        s.cycle_action(actor=self.root,pk=self.cycle_obj.pk,expected_version=self.cycle_obj.version,action='close',reason='Close')
        with CaptureQueriesContext(connection) as captured:result=q.aggregates(self.root,self.cycle_obj.pk,original.target_key,True)
        self.assertLessEqual(len(captured),8)
        self.assertEqual(result['response_count'],2)
        rating=next(r for r in result['questions'] if r['response_type']=='RATING');self.assertEqual(Decimal(rating['average']),4)
        self.assertNotIn('<script>',str(result));self.assertNotIn('response_token',str(result))

    def test_faculty_scope_and_visibility(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.people_master.models import AccountLink
        from apps.tenancy.models import InstitutionModule,Membership,ScopeGrant
        from apps.feedback import selectors as q
        from rest_framework.exceptions import NotFound
        self.questionnaire.questionnaire_type='FACULTY';self.questionnaire.save();self.cycle()
        s.cycle_action(actor=self.root,pk=self.cycle_obj.pk,expected_version=self.cycle_obj.version,action='close',reason='Close')
        teacher=get_user_model().objects.create_user(username='feedback-faculty');teacher.user_permissions.add(Permission.objects.get(codename='view_faculty_results',content_type__app_label='feedback'))
        AccountLink.objects.create(user=teacher,employee=self.employee);member=Membership.objects.create(user=teacher,institution=self.institution);grant=ScopeGrant.objects.create(membership=member,role='TEACHER');InstitutionModule.objects.filter(institution=self.institution).update(feedback=True)
        self.assertEqual(q.faculty_cycles(teacher).count(),1)
        self.assertTrue(q.aggregates(teacher,self.cycle_obj.pk,'faculty:'+str(self.assignment.pk))['suppressed'])
        grant.is_active=False;grant.save()
        with self.assertRaises(NotFound):q.aggregates(teacher,self.cycle_obj.pk,'faculty:'+str(self.assignment.pk))
    def test_key_change_and_end_boundary_fail_closed(self):
        self.cycle();user=self.student();target={'course_offering_id':self.course_offering.pk}
        with override_settings(FEEDBACK_PRIVACY_KEY='another-test-key-0000000000000000000000'):
            with self.assertRaises(s.Conflict):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target=target,answers=self.answers(),key='key-change')
        from unittest.mock import patch
        with patch('apps.feedback.services.timezone.now',return_value=self.cycle_obj.end_at):
            with self.assertRaises(s.Conflict):s.submit(actor=user,cycle_id=self.cycle_obj.pk,target=target,answers=self.answers(),key='end')

    def test_scoped_coordinator_scheduling_lookups(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.tenancy.models import Membership,ScopeGrant,InstitutionModule
        from rest_framework.test import APIClient
        self.activate()
        actor=get_user_model().objects.create_user(username='feedback-coordinator')
        actor.user_permissions.add(Permission.objects.get(codename='manage_cycles',content_type__app_label='feedback'))
        member=Membership.objects.create(user=actor,institution=self.institution)
        grant=ScopeGrant.objects.create(membership=member,role='DEPARTMENT_ADMIN',campus=self.programme.department.campus,department=self.programme.department,record_limits={'programmes':[self.programme.pk]})
        InstitutionModule.objects.filter(institution=self.institution).update(feedback=True)
        client=APIClient();client.force_authenticate(actor)
        for resource,pk in [('questionnaires',self.questionnaire.pk),('programmes',self.programme.pk),('institutions',self.institution.pk)]:
            result=client.get('/api/v1/feedback/'+resource+'/');self.assertEqual(result.status_code,200,result.data)
            self.assertIn(str(pk),[row['id'] for row in result.data['results']])
        self.assertEqual(client.get('/api/v1/feedback/questions/').data['results'],[])
        self.assertEqual(client.get('/api/v1/feedback/terms/').status_code,200)
        grant.is_active=False;grant.save()
        self.assertEqual(client.get('/api/v1/feedback/questionnaires/').data['results'],[])
        self.assertEqual(client.get('/api/v1/feedback/programmes/').data['results'],[])
