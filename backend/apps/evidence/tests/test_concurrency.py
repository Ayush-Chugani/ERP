from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.evidence import services as s
from apps.evidence.models import EvidenceDocumentVersion
from apps.identity_access.models import UserRoleAssignment

from . import test_module


@override_settings(
    EVIDENCE_ENABLED=True,
    DOCUMENTS_EXIT_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class EvidenceConcurrency(TransactionTestCase):
    def setUp(self):
        test_module.EvidenceTests.setUp(self)

    def _fixture_teardown(self):
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError("Isolated test database required.")
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            try:
                for table in (
                    "evidence_document_audit",
                    "platform_evidence_command_receipt",
                    "platform_evidence_expiry_notice",
                    "evidence_document_tag",
                    "evidence_document_version",
                    "evidence_document",
                    "evidence_tag",
                ):
                    cursor.execute("TRUNCATE TABLE " + table)
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        super()._fixture_teardown()

    def test_two_replacements_cannot_publish_two_current_versions(self):
        row = s.create_evidence_with_file(
            actor=self.root,
            values=self.values,
            upload=test_module.EvidenceTests.upload(self),
            key="create",
        )
        other = get_user_model().objects.create_superuser(
            username="m33-other", password="test-only"
        )
        UserRoleAssignment.objects.create(
            user=other,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=self.grant.valid_from,
        )
        token = s.version(row)
        barrier = Barrier(2)

        def replace(actor_id):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    s.replace_evidence_file(
                        actor=actor,
                        document_id=row.pk,
                        upload=test_module.EvidenceTests.upload(self),
                        change_reason="Concurrent correction",
                        expected_version=token,
                        key=f"replace-{actor_id}",
                    )
                    return "saved"
                except s.Conflict:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                f.result(timeout=30)
                for f in [pool.submit(replace, a.pk) for a in (self.root, other)]
            ]
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(
            EvidenceDocumentVersion.objects.filter(evidence_document=row).count(), 2
        )
        self.assertEqual(
            EvidenceDocumentVersion.objects.filter(
                evidence_document=row, is_current=True
            ).count(),
            1,
        )

    def test_empty_native_reverse_and_reinstall(self):
        from django.db.migrations.executor import MigrationExecutor

        MigrationExecutor(connection).migrate([("evidence", None)])
        self.assertNotIn("evidence_document", connection.introspection.table_names())
        MigrationExecutor(connection).migrate(
            [("evidence", "0003_source_query_indexes")]
        )
        self.assertIn("evidence_document", connection.introspection.table_names())
