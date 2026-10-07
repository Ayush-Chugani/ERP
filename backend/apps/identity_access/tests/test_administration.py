from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.identity_access.seeding import seed
from apps.identity_access import models as m, services

@override_settings(IDENTITY_ACCESS_ENABLED=True)
class AdministrationTests(TestCase):
    def setUp(self):
        seed(); self.now=timezone.now().replace(microsecond=0)
        self.actor=get_user_model().objects.create_user(username='security-operator',password='operator-secret')
        self.target=get_user_model().objects.create_user(username='target')
        m.UserRoleAssignment.objects.create(user=self.actor,role=m.Role.objects.get(role_code='SUPER_ADMIN'),scope_type='GLOBAL',valid_from=self.now)
        self.proof={'password':'operator-secret'}

    def test_assignment_requires_step_up_and_independent_target(self):
        role=m.Role.objects.get(role_code='STUDENT')
        args=dict(actor=self.actor,role_id=role.pk,scope_type='SELF',entity_id=self.target.pk,valid_from=self.now,justification='Verified student')
        with self.assertRaises(PermissionDenied): services.assign_role(user_id=self.target.pk,proof={},**args)
        with self.assertRaises(PermissionDenied): services.assign_role(user_id=self.actor.pk,proof=self.proof,**args)
        row=services.assign_role(user_id=self.target.pk,proof=self.proof,**args)
        self.assertEqual(row.scope_entity_id,self.target.pk)
        services.end_assignment(actor=self.actor,pk=row.pk,proof=self.proof,justification='Access ended')
        row.refresh_from_db(); self.assertEqual(row.assignment_status,'REVOKED')
        self.assertEqual(m.ActivityAudit.objects.count(),2)

    def test_cannot_edit_own_role_matrix(self):
        with self.assertRaises(PermissionDenied):
            services.set_matrix(actor=self.actor,role_id=m.Role.objects.get(role_code='SUPER_ADMIN').pk,entries=[],proof=self.proof,justification='Test')
