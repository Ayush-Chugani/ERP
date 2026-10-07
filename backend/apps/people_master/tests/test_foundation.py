from types import SimpleNamespace
from django.apps import apps
from django.test import SimpleTestCase, override_settings
from apps.people_master.permissions import PeopleModuleEnabled
from apps.people_master import public
from apps.people_master.urls import urlpatterns


class PeopleFoundationTests(SimpleTestCase):
    def test_registered_but_no_premature_domain_routes(self):
        self.assertEqual(
            apps.get_app_config("people_master").name, "apps.people_master"
        )
        self.assertTrue(urlpatterns)
        self.assertFalse(
            any(hasattr(value, "objects") for value in vars(public).values())
        )

    @override_settings(PEOPLE_MASTER_ENABLED=False)
    def test_disabled_module_denies_even_authenticated_user(self):
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=True, is_active=True)
        )
        self.assertFalse(PeopleModuleEnabled().has_permission(request, None))

    @override_settings(PEOPLE_MASTER_ENABLED=True)
    def test_inactive_and_anonymous_users_denied(self):
        for authenticated, active in [(False, True), (True, False)]:
            request = SimpleNamespace(
                user=SimpleNamespace(is_authenticated=authenticated, is_active=active)
            )
            self.assertFalse(PeopleModuleEnabled().has_permission(request, None))
