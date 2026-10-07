from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity_access import security, models as m

@override_settings(IDENTITY_ACCESS_SECURITY_ENABLED=True, IDENTITY_ACCESS_LOGIN_LIMIT=2)
class SecurityTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='secure',password='current-valid-password-123')

    def test_failed_login_evidence_survives_and_lock_expires(self):
        for unused in range(2):
            with self.assertRaises(AuthenticationFailed): security.login(username='secure',password='wrong')
        self.user.refresh_from_db(); self.assertEqual(self.user.failed_login_count,2)
        self.assertIsNotNone(self.user.locked_until)
        self.assertEqual(m.LoginAudit.objects.filter(was_successful=False).count(),2)
        with self.assertRaises(AuthenticationFailed): security.login(username='secure',password='current-valid-password-123')
        get_user_model().objects.filter(pk=self.user.pk).update(locked_until=timezone.now()-timedelta(seconds=1))
        user,session=security.login(username='secure',password='current-valid-password-123')
        self.assertEqual(user.failed_login_count,0); self.assertTrue(session)

    def test_mfa_without_provider_fails_closed(self):
        self.user.multi_factor_enabled=True; self.user.save()
        with self.assertRaises(AuthenticationFailed): security.login(username='secure',password='current-valid-password-123')

    def test_password_reuse_and_old_access_revocation(self):
        token=RefreshToken.for_user(self.user); security.token_claims(self.user,token,'test-session')
        security.change_password(actor=self.user,current_password='current-valid-password-123',new_password='a-different-valid-password-123')
        self.user.refresh_from_db()
        with self.assertRaises(AuthenticationFailed): security.validate_session(self.user,token)
        with self.assertRaises(ValidationError): security.change_password(actor=self.user,current_password='a-different-valid-password-123',new_password='current-valid-password-123')
        client=APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer '+str(token.access_token))
        self.assertEqual(client.get('/api/v1/auth/me/').status_code,401)

    def test_reset_token_is_one_use(self):
        token=default_token_generator.make_token(self.user)
        security.reset_password(user_id=self.user.pk,token=token,new_password='a-different-valid-password-123')
        with self.assertRaises(PermissionDenied): security.reset_password(user_id=self.user.pk,token=token,new_password='third-valid-password-123')

    def test_nested_audit_redaction(self):
        from apps.identity_access.audit import record
        row=record(actor=self.user,action='CONFIGURE',details={'nested':{'password':'never retain','token':'never retain'},'event':'test'})
        self.assertNotIn('never retain',str(row.details))

    def test_framework_password_change_also_revokes_existing_access(self):
        token=RefreshToken.for_user(self.user);security.token_claims(self.user,token,'framework-change')
        self.user.set_password('framework-updated-password');self.user.save(update_fields=['password'])
        with self.assertRaises(AuthenticationFailed):security.validate_session(self.user,token)
    def test_http_login_audit_and_refresh_recheck_security_state(self):
        client=APIClient(enforce_csrf_checks=True)
        csrf=client.get('/api/v1/auth/csrf/').json()['csrfToken']
        headers={'HTTP_ORIGIN':'http://testserver','HTTP_X_CSRFTOKEN':csrf}
        bad=client.post('/api/v1/auth/login/',{'username':'secure','password':'wrong'},format='json',**headers)
        self.assertEqual(bad.status_code,401)
        self.assertEqual(m.LoginAudit.objects.filter(was_successful=False).count(),1)
        response=client.post('/api/v1/auth/login/',{'username':'secure','password':'current-valid-password-123'},format='json',**headers)
        self.assertEqual(response.status_code,200)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+response.json()['access'])
        self.assertEqual(client.get('/api/v1/auth/me/').status_code,200)
        get_user_model().objects.filter(pk=self.user.pk).update(account_status='DISABLED')
        self.assertEqual(client.get('/api/v1/auth/me/').status_code,401)
        headers['HTTP_X_CSRFTOKEN']=response.json()['csrfToken']
        self.assertEqual(client.post('/api/v1/auth/refresh/',{},format='json',**headers).status_code,401)
