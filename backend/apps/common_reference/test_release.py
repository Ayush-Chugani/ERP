"""Release workflow through real JWT/CSRF endpoints (no force_authenticate)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from apps.core.models import ReferenceAuditEvent


class ReleaseWorkflowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='release-test', password='test-password')
        self.user.user_permissions.set(Permission.objects.filter(
            content_type__app_label='common_reference', codename__in=[
                'maintain_reference', 'view_country', 'add_country', 'change_country',
                'view_state', 'add_state', 'change_state']))
        self.client = APIClient(enforce_csrf_checks=True)

    def auth_post(self, action, data=None):
        csrf = self.client.get('/api/v1/auth/csrf/').json()['csrfToken']
        return self.client.post(f'/api/v1/auth/{action}/', data or {}, format='json',
                                HTTP_ORIGIN='http://testserver', HTTP_X_CSRFTOKEN=csrf)

    def test_login_catalogue_history_audit_revocation_and_logout(self):
        login = self.auth_post('login', {'username': self.user.username, 'password': 'test-password'})
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
        self.assertEqual(self.client.get('/api/v1/auth/me/').json()['user_id'], self.user.pk)
        country = self.client.post('/api/v1/reference/countries/', {'iso_code': 'IN', 'country_name': 'India'}, format='json')
        self.assertEqual(country.status_code, 201, country.data)
        country_id = country.json()['country_id']
        state = self.client.post('/api/v1/reference/states/', {'country_id': country_id, 'state_code': 'MH', 'state_name': 'Maharashtra'}, format='json')
        self.assertEqual(state.status_code, 201)
        state_id = state.json()['state_id']
        self.assertEqual(self.client.patch(f'/api/v1/reference/countries/{country_id}/', {'is_active': False}, format='json').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/reference/states/').json()['count'], 0)
        self.assertFalse(self.client.get(f'/api/v1/reference/states/{state_id}/').json()['effective_active'])
        self.assertEqual(self.client.patch(f'/api/v1/reference/states/{state_id}/', {'country_id': country_id, 'state_name': 'Historical label'}, format='json').status_code, 200)
        self.assertEqual(ReferenceAuditEvent.objects.filter(actor=self.user).count(), 4)
        refresh = self.auth_post('refresh')
        self.assertEqual(refresh.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + refresh.json()['access'])
        self.user.user_permissions.remove(Permission.objects.get(codename='maintain_reference'))
        self.assertEqual(self.client.patch(f'/api/v1/reference/countries/{country_id}/', {'is_active': True}, format='json').status_code, 403)
        self.assertEqual(self.auth_post('logout').status_code, 204)
        self.assertEqual(self.auth_post('refresh').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/v1/reference/countries/').status_code, 401)
