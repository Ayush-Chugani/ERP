from datetime import timedelta
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import connection
from apps.identity_access import models as m,services
from apps.identity_access.seeding import seed
from apps.identity_access.evaluator import has_permission

@override_settings(IDENTITY_ACCESS_ENABLED=True)
class OverrideRevocationTests(TestCase):
    def test_future_override_can_be_revoked_without_rewriting_dates(self):
        seed();actor=get_user_model().objects.create_user(username='revoke-operator',password='operator-password')
        target=get_user_model().objects.create_user(username='revoke-target')
        now=timezone.now().replace(microsecond=0)
        m.UserRoleAssignment.objects.create(user=actor,role=m.Role.objects.get(role_code='SUPER_ADMIN'),scope_type='GLOBAL',valid_from=now-timedelta(seconds=2))
        row=services.grant_override(actor=actor,user_id=target.pk,permission_id=m.Permission.objects.get(permission_code='STUDENT.ALL.READ').pk,scope_type='SELF',entity_id=target.pk,effect='ALLOW',valid_from=now+timedelta(days=1),valid_to=now+timedelta(days=2),proof={'password':'operator-password'},justification='Future temporary access')
        start=row.valid_from
        services.end_override(actor=actor,pk=row.pk,proof={'password':'operator-password'},justification='Cancelled before start')
        row.refresh_from_db();self.assertEqual(row.valid_from,start);self.assertIsNotNone(row.revoked_at)
        self.assertFalse(has_permission(target,'STUDENT.ALL.READ','SELF',target.pk,at=now+timedelta(days=1,hours=1)))
        # Move an explicitly revoked row into the current window to test SQL exclusion too.
        m.UserPermissionOverride.objects.filter(pk=row.pk).update(valid_from=now-timedelta(hours=1))
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM v_effective_user_permission WHERE user_id=%s',[target.pk]);self.assertEqual(cursor.fetchone()[0],0)
