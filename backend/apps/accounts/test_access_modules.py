"""`/auth/me/` exposes IAM module codes so the UI can hide navigation the user cannot use."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.identity_access import models as iam
from .views import access_modules


class AccessModulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="faculty1", password="x")
        self.root = User.objects.create_superuser(username="root1", password="x")
        action = iam.AccessAction.objects.create(action_code="T_READ", action_name="Test read")
        self.perms = {}
        for code in ("T_AWARDS", "T_REPORTS"):
            module = iam.AccessModule.objects.create(module_code=code, module_name=code.title())
            resource = iam.AccessResource.objects.create(access_module=module, resource_code="ACTIVITY", resource_name="Activity")
            self.perms[code] = iam.Permission.objects.create(
                access_resource=resource, access_action=action, permission_code=f"{code}.ACTIVITY.READ", permission_name=code)
        self.role = iam.Role.objects.create(role_code="T_ROLE", role_name="Test role", role_category="FACULTY", role_level="GLOBAL")
        iam.RolePermission.objects.create(role=self.role, permission=self.perms["T_AWARDS"], permission_effect="ALLOW")
        iam.RolePermission.objects.create(role=self.role, permission=self.perms["T_REPORTS"], permission_effect="DENY")

    def assign(self, **over):
        values = dict(user=self.user, role=self.role, scope_type="GLOBAL", assignment_status="ACTIVE",
                      valid_from=timezone.now() - timedelta(minutes=1))
        values.update(over)
        return iam.UserRoleAssignment.objects.create(**values)

    def test_superuser_needs_no_list(self):
        self.assertEqual(access_modules(self.root), [])

    def test_active_allow_grants_only_allowed_modules(self):
        self.assertEqual(access_modules(self.user), [])
        self.assign()
        self.assertEqual(access_modules(self.user), ["T_AWARDS"])

    def test_expired_and_revoked_assignments_grant_nothing(self):
        self.assign(valid_from=timezone.now() - timedelta(days=5), valid_to=timezone.now() - timedelta(days=1))
        self.assertEqual(access_modules(self.user), [])
        iam.UserRoleAssignment.objects.all().delete()
        self.assign(assignment_status="REVOKED")
        self.assertEqual(access_modules(self.user), [])

    def test_me_endpoint_returns_modules(self):
        self.assign()
        client = APIClient()
        client.force_authenticate(self.user)
        body = client.get("/api/v1/auth/me/").json()
        self.assertEqual(body["access_modules"], ["T_AWARDS"])
        self.assertEqual(body["username"], "faculty1")
