from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.identity_access.models import UserRoleAssignment
from apps.professional_contributions import services as s
from apps.professional_contributions.models import StaffProfessionalContribution

from . import test_module


@override_settings(
    PROFESSIONAL_CONTRIBUTIONS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConcurrentAward(TransactionTestCase):
    def setUp(self):
        test_module.ContributionTests.setUp(self)

    def _fixture_teardown(self):
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError("Isolated test database required")
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE platform_professional_contributions_status_history"
            )
        super()._fixture_teardown()

    def test_simultaneous_edits_require_fresh_version(self):
        row = s.save_activity(
            self.root, self.values, context=self.context, key="create"
        )
        other = get_user_model().objects.create_user(
            username="professional_contributions-editor"
        )
        UserRoleAssignment.objects.create(
            user=other,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=self.grant.valid_from,
        )
        token = s.version(row.pk)
        barrier = Barrier(2)

        def edit(actor_id):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    s.update_activity(
                        actor,
                        row.pk,
                        {"title_topic": str(actor_id)},
                        expected_version=token,
                    )
                    return "saved"
                except s.Conflict:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(edit, a.pk) for a in (self.root, other)]
            results = [f.result(timeout=30) for f in futures]
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(StaffProfessionalContribution.objects.count(), 1)

    def test_empty_reverse_and_reinstall(self):
        from django.db.migrations.executor import MigrationExecutor

        # Only this module is reversed on an isolated test database, never shared masters.
        executor = MigrationExecutor(connection)
        executor.migrate([("professional_contributions", None)])
        self.assertNotIn(
            "staff_professional_contribution", connection.introspection.table_names()
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("professional_contributions", "0002_retain_status_history")])
        self.assertIn(
            "staff_professional_contribution", connection.introspection.table_names()
        )
