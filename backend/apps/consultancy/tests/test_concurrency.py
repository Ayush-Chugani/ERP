from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.consultancy import services as s
from apps.consultancy.models import ConsultancyProject, ProjectReceipt
from apps.identity_access.models import UserRoleAssignment

from . import test_module


@override_settings(
    CONSULTANCY_ENABLED=True,
    RESEARCH_PROPOSALS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConcurrentConsultancy(TransactionTestCase):
    def setUp(self):
        test_module.ConsultancyTests.setUp(self)

    def _fixture_teardown(self):
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError("Isolated test database required")
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            try:
                for table in (
                    "platform_consultancy_receipt_void",
                    "platform_consultancy_receipt",
                    "platform_consultancy_status_history",
                ):
                    cursor.execute("TRUNCATE TABLE " + table)
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        super()._fixture_teardown()

    def test_simultaneous_receipts_require_fresh_version_and_preserve_totals(self):
        row = s.save_activity(
            self.root, self.values, context=self.context, key="create"
        )
        other = get_user_model().objects.create_user(username="consultancy-finance")
        UserRoleAssignment.objects.create(
            user=other,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=self.grant.valid_from,
        )
        version = s.version(row.pk)
        barrier = Barrier(2)

        def add(actor_id):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    s.extension(
                        actor,
                        row.pk,
                        "receipts",
                        {
                            "receipt_date": "2026-02-01",
                            "amount": "125.01",
                            "currency_code": "INR",
                            "reference_number": str(actor_id),
                        },
                        expected_version=version,
                        reason="Payment received",
                        key="receipt",
                    )
                    return "saved"
                except s.Conflict:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(add, actor.pk) for actor in (self.root, other)]
            results = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(ProjectReceipt.objects.count(), 1)
        self.assertEqual(
            str(ConsultancyProject.objects.get(pk=row.pk).amount_received), "125.01"
        )
