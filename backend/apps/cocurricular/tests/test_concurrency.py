from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.cocurricular import services as s
from apps.cocurricular.models import CocurricularActivity
from apps.identity_access.models import UserRoleAssignment

from . import test_module


@override_settings(
    COCURRICULAR_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConcurrentCocurricular(TransactionTestCase):
    def setUp(self):
        test_module.CocurricularTests.setUp(self)

    def _fixture_teardown(self):
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError("Isolated test database required")
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE platform_cocurricular_status_history")
        super()._fixture_teardown()

    def test_simultaneous_edits_require_fresh_version(self):
        row = s.save_activity(
            self.root, self.values, context=self.context, key="create"
        )
        other = get_user_model().objects.create_user(username="cocurricular-editor")
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
                        {"event_name": str(actor_id)},
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
        self.assertEqual(CocurricularActivity.objects.count(), 1)

    def test_empty_reverse_and_reinstall(self):
        from django.db.migrations.executor import MigrationExecutor

        # Only this module is reversed on an isolated test database, never shared masters.
        executor = MigrationExecutor(connection)
        executor.migrate([("cocurricular", None)])
        self.assertNotIn(
            "cocurricular_activity", connection.introspection.table_names()
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("cocurricular", "0002_retain_status_history")])
        self.assertIn("cocurricular_activity", connection.introspection.table_names())
