from unittest.mock import patch
from dataclasses import replace
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .registry import MODULES, validate_registry
from .pagination import BoundedPagination

class FoundationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="tester", password="long-test-password")

    def test_auth_default_and_custom_jwt_identity(self):
        self.assertEqual(self.client.get("/api/v1/").status_code, 401)
        token = RefreshToken.for_user(self.user)
        self.assertEqual(str(token["user_id"]), str(self.user.user_id))
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token.access_token))
        self.assertEqual(self.client.get("/api/v1/").status_code, 200)
        token.blacklist()
        with self.assertRaises(TokenError):
            RefreshToken(str(token))

    def test_groups_allow_multiple_and_grant_nothing(self):
        call_command("seed_role_groups", verbosity=0)
        call_command("seed_role_groups", verbosity=0)
        self.user.groups.add(*Group.objects.filter(name__in=["Admin", "Teacher"]))
        self.assertEqual(self.user.groups.count(), 2)
        self.assertFalse(self.user.has_perm("accounts.manage_platform_access"))
        self.assertEqual(Group.objects.count(), 3)

    def test_health_is_public_and_readiness_redacts_failures(self):
        self.assertEqual(self.client.get("/api/v1/core/live/").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/v1/core/ready/").status_code, 200)
        with patch("apps.core.views.connection.cursor", side_effect=RuntimeError("secret-password")):
            response = self.client.get("/api/v1/core/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-password", str(response.content))

    def test_bounded_stable_pagination(self):
        request = Request(APIRequestFactory().get("/", {"page_size": 9999}))
        pagination = BoundedPagination()
        self.assertEqual(pagination.get_page_size(request), 100)
        get_user_model().objects.create_user(username="another")
        rows = pagination.paginate_queryset(get_user_model().objects.order_by(), request)
        self.assertEqual([r.pk for r in rows], sorted(r.pk for r in rows))

    def test_registry_rejects_invalid_descriptors(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_registry(MODULES + (MODULES[0],))
        with self.assertRaises(ImproperlyConfigured):
            validate_registry((replace(MODULES[0], dependencies=("UNKNOWN",)),))
        with self.assertRaises(ImproperlyConfigured):
            validate_registry((replace(MODULES[0], dependencies=("CORE",)),))

    def test_error_shape_and_explicit_cors(self):
        response = self.client.get("/api/v1/")
        self.assertEqual(set(response.json()["error"]), {"code", "message", "details"})
        with override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"]):
            accepted = self.client.get("/api/v1/core/live/", HTTP_ORIGIN="http://localhost:5173")
            rejected = self.client.get("/api/v1/core/live/", HTTP_ORIGIN="https://untrusted.invalid")
        self.assertEqual(accepted["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertNotIn("Access-Control-Allow-Origin", rejected)
