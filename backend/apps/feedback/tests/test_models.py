from django.test import TestCase,override_settings
from django.db import transaction,IntegrityError
from django.db.models.deletion import ProtectedError
from apps.teaching_timetable.tests import test_services as fixtures
from apps.feedback import models as m
@override_settings(ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,TEACHING_TIMETABLE_ENABLED=True)
class ModelTests(TestCase):
    def setUp(self):
        fixtures.TimetableTests.setUp(self)
        self.category=m.Category.objects.create(institution=self.institution,category_code='M11',category_name='Feedback',actor=self.root)
    def test_defaults_uniqueness_and_protection(self):
        self.assertTrue(self.category.is_active);self.assertEqual(str(self.category),'Feedback')
        question=m.Question.objects.create(feedback_category=self.category,question_text='Quality?',response_type='TEXT',text_limit=1000,actor=self.root)
        with self.assertRaises(ProtectedError):self.category.delete()
        with self.assertRaises(IntegrityError),transaction.atomic():m.Category.objects.create(institution=self.institution,category_code='M11',category_name='Another',actor=self.root)
        with self.assertRaises(IntegrityError),transaction.atomic():m.Question.objects.filter(pk=question.pk).update(response_type='INVALID')
    def test_rating_model_validation(self):
        from django.core.exceptions import ValidationError
        question=m.Question(feedback_category=self.category,question_text='Rating?',response_type='RATING',actor=self.root)
        with self.assertRaises(ValidationError):question.full_clean()
