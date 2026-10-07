from django.test import SimpleTestCase
from django.apps import apps
from apps.academic_calendar import public


class FoundationTests(SimpleTestCase):
    def test_app_and_public_import_without_database(self):
        self.assertEqual(apps.get_app_config('academic_calendar').name, 'apps.academic_calendar')
        self.assertIsNotNone(public)
