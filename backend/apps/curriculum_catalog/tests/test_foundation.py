from pathlib import Path
from django.apps import apps
from django.test import SimpleTestCase


class FoundationTests(SimpleTestCase):
    def test_import_and_dependency_boundary(self):
        from apps.curriculum_catalog.integrations.upstream import OrganizationContext

        self.assertEqual(
            apps.get_app_config("curriculum_catalog").name, "apps.curriculum_catalog"
        )
        self.assertIsNotNone(OrganizationContext)
        root = Path(__file__).parents[1]
        for path in root.glob("*.py"):
            code = path.read_text(encoding="utf-8-sig")
            for forbidden in (
                "from apps.organization.models",
                "from apps.tenancy.models",
                "from apps.academic_calendar.models",
            ):
                self.assertNotIn(forbidden, code, str(path))
