from django.apps import apps
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import AnonymousUser
from django.db import connection, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import NotFound, PermissionDenied
from apps.common_reference.models import Country
from apps.employee_hr import models as m
from apps.employee_hr.permissions import require_enabled, require_permission
from apps.employee_hr.migrations._reference_ddl import DDL
from apps.employee_hr.migrations._reference_schema import verify

class ScaffoldTests(SimpleTestCase):
    def test_existing_owners_and_disabled_activation(self):
        self.assertEqual(apps.get_app_config('employee_hr').name,'apps.employee_hr')
        with self.assertRaises(NotFound): require_enabled()

    @override_settings(EMPLOYEE_HR_ENABLED=True, IDENTITY_ACCESS_ENABLED=True,
                       IDENTITY_ACCESS_SECURITY_ENABLED=True)
    def test_anonymous_principals_fail_closed(self):
        for actor in (None, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                require_permission(actor, 'EMPLOYEE.PAN.READ', scopes=[])

class ReferenceContractTests(TestCase):
    def test_all_eight_native_schema_contracts(self):
        self.assertEqual(len(DDL),8)
        with connection.cursor() as cursor:
            for ddl in DDL:self.assertTrue(verify(cursor,ddl))

    def test_reference_code_and_name_uniqueness(self):
        m.StudyMode.objects.create(pk=200,mode_code='SYNTHETIC',mode_name='Synthetic mode')
        for values in [dict(mode_code='synthetic',mode_name='Other'),dict(mode_code='OTHER',mode_name='Synthetic mode')]:
            with self.assertRaises(IntegrityError),transaction.atomic():m.StudyMode.objects.create(pk=201,**values)

    def test_country_composite_unique_and_nullable_semantics(self):
        country=Country.objects.create(country_name='Synthetic country',iso_code='XZ')
        values=dict(institution_name='Synthetic Institute',city='Test City',country=country)
        m.EducationInstitution.objects.create(**values)
        with self.assertRaises(IntegrityError),transaction.atomic():m.EducationInstitution.objects.create(**values)
        # SQL NULLs remain distinct; do not silently coalesce absent country/city.
        for unused in range(2):m.EducationInstitution.objects.create(institution_name='Incomplete institute')
        with self.assertRaises(ProtectedError):country.delete()

    def test_server_defaults_and_enum_validation(self):
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO qualification_level (level_code,level_name) VALUES ('SYNTHETIC','Synthetic level')")
        row=m.QualificationLevel.objects.get(level_code='SYNTHETIC')
        self.assertTrue(row.is_active);self.assertFalse(row.is_terminal_degree);self.assertEqual(row.display_order,0)
        self.assertIsNotNone(row.created_at);self.assertIsNotNone(row.updated_at)
        org=m.PreviousOrganizationType.objects.create(pk=201,type_code='SYNTHETIC',type_name='Synthetic organization')
        self.assertEqual(org.classification,'OTHER')
        from django.core.exceptions import ValidationError
        org.classification='INVALID'
        with self.assertRaises(ValidationError):org.full_clean()
