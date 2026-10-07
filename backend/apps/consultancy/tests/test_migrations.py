from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ConsultancyMigrationTests(TransactionTestCase):
    def test_empty_installation_reverses_and_reinstalls_without_touching_other_modules(
        self,
    ):
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError("Isolated test DB required")
        target = [("consultancy", "0003_retention")]
        try:
            MigrationExecutor(connection).migrate([("consultancy", None)])
            self.assertNotIn(
                "consultancy_project", connection.introspection.table_names()
            )
            self.assertIn(
                "funded_research_project", connection.introspection.table_names()
            )
        finally:
            MigrationExecutor(connection).migrate(target)
        self.assertIn("consultancy_project", connection.introspection.table_names())
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE consultancy_project")
            ddl = cursor.fetchone()[1].lower()
        for fragment in (
            "decimal(16,2)",
            "bigint unsigned",
            "chk_consultancy_dates",
            "chk_consultancy_amounts",
            "utf8mb4_unicode_ci",
        ):
            self.assertIn(fragment, ddl)
