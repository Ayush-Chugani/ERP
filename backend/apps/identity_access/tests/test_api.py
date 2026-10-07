from datetime import timedelta
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from apps.identity_access.seeding import seed
from apps.identity_access import models as m

class EndpointTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='api-security',is_superuser=True)
        self.client=APIClient()
    def test_anonymous_and_staged_denial(self):
        self.assertEqual(self.client.get('/api/v1/security/users/').status_code,401)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/v1/security/users/').status_code,404)
    @override_settings(IDENTITY_ACCESS_ENABLED=True)
    def test_superuser_is_not_business_authority_and_fields_are_safe(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/v1/security/users/').status_code,403)
        seed();m.UserRoleAssignment.objects.create(user=self.user,role=m.Role.objects.get(role_code='SECURITY_ADMIN'),scope_type='GLOBAL',valid_from=timezone.now()-timedelta(seconds=2))
        response=self.client.get('/api/v1/security/users/')
        self.assertEqual(response.status_code,200)
        row=response.json()['results'][0]
        self.assertNotIn('password',row);self.assertNotIn('security_version',row)
        self.assertEqual(response['Cache-Control'],'no-store')
