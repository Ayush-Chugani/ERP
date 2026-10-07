from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from apps.student_support import models as m
from apps.student_support import services as s

from . import test_workflows as fixtures


@override_settings(STUDENT_SUPPORT_ENABLED=True)
class TransactionTests(TransactionTestCase):
    setUp = fixtures.SupportTests.setUp
    actor = fixtures.SupportTests.actor
    grievance = fixtures.SupportTests.grievance

    def parallel(self, fn):
        barrier = Barrier(2)

        def worker(n):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return fn(n)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return [
                future.result(timeout=45)
                for future in [pool.submit(worker, 0), pool.submit(worker, 1)]
            ]

    def test_simultaneous_transitions_have_one_winner(self):
        obj = self.grievance()

        def work(n):
            try:
                s.grievance_action(
                    actor=self.root,
                    pk=obj.pk,
                    expected_status="SUBMITTED",
                    action="review" if n else "reject",
                    notes="Rationale",
                )
                return "saved"
            except s.Conflict:
                return "conflict"

        self.assertCountEqual(self.parallel(work), ["saved", "conflict"])
        self.assertEqual(m.GrievanceAction.objects.filter(grievance=obj).count(), 2)

    def test_concurrent_numbers_are_unique(self):
        results = self.parallel(lambda n: self.grievance().grievance_number)
        self.assertEqual(len(set(results)), 2)
        self.assertEqual(m.GrievanceAction.objects.count(), 2)

    def test_state_rollback_preserves_and_readopts_canonical_tables(self):
        obj = self.grievance()
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([("student_support", None)])
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM grievance WHERE grievance_id=%s", [obj.pk]
                )
                self.assertEqual(cursor.fetchone()[0], 1)
            MigrationExecutor(connection).migrate(leaves)
            self.assertTrue(m.Grievance.objects.filter(pk=obj.pk).exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)

    def test_adoption_refuses_schema_drift(self):
        from apps.student_support.migrations._canonical import DDL, verify

        sql = next(s for s in DDL if "CREATE TABLE grievance_category " in s)
        with connection.cursor() as cursor, self.assertRaises(RuntimeError):
            verify(cursor, sql.replace("VARCHAR(30)", "VARCHAR(31)"))
