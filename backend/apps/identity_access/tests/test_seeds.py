from django.test import TestCase
from apps.identity_access import models as m
from apps.identity_access.seeding import seed, catalogue

class CatalogueTests(TestCase):
    def test_exact_seed_matrix_idempotency_and_no_user_assignments(self):
        seed(); seed(); source=catalogue()
        self.assertEqual(m.Permission.objects.count(),220)
        self.assertEqual(m.Role.objects.count(),32)
        self.assertEqual(m.RolePermission.objects.count(),1732)
        self.assertEqual(set(m.Permission.objects.filter(is_sensitive=True).values_list('permission_code',flat=True)),set(source['sensitive_permissions']))
        for role, expected in source['role_permissions'].items():
            self.assertEqual(set(m.RolePermission.objects.filter(role__role_code=role).values_list('permission__permission_code',flat=True)),set(expected),role)
        self.assertFalse(m.UserRoleAssignment.objects.exists())
        grant=m.RolePermission.objects.first(); grant.permission_effect='DENY'; grant.save()
        seed(); grant.refresh_from_db(); self.assertEqual(grant.permission_effect,'DENY')
