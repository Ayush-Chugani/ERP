from datetime import timedelta
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.identity_access import models as m,impersonation
from apps.identity_access.evaluator import Scope
from apps.identity_access.seeding import seed

@override_settings(IDENTITY_ACCESS_ENABLED=True)
class SupportSessionTests(TestCase):
    def setUp(self):
        seed();self.actor=get_user_model().objects.create_user(username='support-actor',password='support-secret')
        self.target=get_user_model().objects.create_user(username='support-target')
        now=timezone.now()-timedelta(seconds=2)
        m.UserRoleAssignment.objects.create(user=self.actor,role=m.Role.objects.get(role_code='SUPER_ADMIN'),scope_type='GLOBAL',valid_from=now)
        m.UserRoleAssignment.objects.create(user=self.target,role=m.Role.objects.get(role_code='STUDENT'),scope_type='SELF',valid_from=now)
    def test_intersection_read_only_owner_and_revocation(self):
        session=impersonation.start(actor=self.actor,target_id=self.target.pk,proof={'password':'support-secret'},justification='Support request')
        args=dict(actor=self.actor,session_id=session.pk,actor_scopes=[Scope('GLOBAL',0)],target_scopes=[Scope('SELF',self.target.pk)])
        self.assertTrue(impersonation.allowed(code='STUDENT.ALL.READ',**args))
        self.assertFalse(impersonation.allowed(code='STUDENT.ALL.UPDATE',**args))
        self.assertFalse(impersonation.allowed(code='IAM.ALL.READ',**args))
        with self.assertRaises(PermissionDenied): impersonation.context(actor=self.target,session_id=session.pk)
        with self.assertRaises(PermissionDenied): impersonation.start(actor=self.actor,target_id=self.target.pk,proof={'password':'support-secret'},justification='Nested')
        impersonation.end(actor=self.actor,session_id=session.pk)
        with self.assertRaises(PermissionDenied): impersonation.context(actor=self.actor,session_id=session.pk)
        self.assertEqual(set(m.ActivityAudit.objects.values_list('user_id',flat=True)),{self.actor.pk})
