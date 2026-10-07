from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from django.test import TransactionTestCase,override_settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from apps.identity_access.security import login
from apps.identity_access.models import LoginAudit

@override_settings(IDENTITY_ACCESS_SECURITY_ENABLED=True,IDENTITY_ACCESS_LOGIN_LIMIT=5)
class LockoutRaceTests(TransactionTestCase):
    def test_concurrent_failed_attempts_are_not_lost(self):
        user=get_user_model().objects.create_user(username='race-lockout',password='real-password')
        def attempt(unused):
            close_old_connections()
            try:
                try: login(username='race-lockout',password='wrong')
                except AuthenticationFailed: return True
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(attempt,range(2))),[True,True])
        user.refresh_from_db();self.assertEqual(user.failed_login_count,2)
        self.assertEqual(LoginAudit.objects.filter(user=user,was_successful=False).count(),2)
