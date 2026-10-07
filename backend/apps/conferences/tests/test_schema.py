import importlib
import re

from django.apps import apps
from django.db import connection
from django.test import TestCase


class SchemaTests(TestCase):
    def test_all_six_source_tables_and_foreign_keys(self):
        with connection.cursor() as cursor:
            for app, module in [
                ("conferences", "_ddl"),
                ("staff_profile", "_conference_ddl"),
            ]:
                for ddl in importlib.import_module(
                    f"apps.{app}.migrations.{module}"
                ).DDL:
                    table = re.search(r"CREATE TABLE (\w+)", ddl)[1]
                    model = next(
                        m
                        for m in apps.get_app_config(app).get_models()
                        if m._meta.db_table == table
                    )
                    fields = {f.column: f for f in model._meta.local_fields if f.column}
                    cursor.execute(
                        "SELECT COLUMN_NAME,COLUMN_TYPE,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                        [table],
                    )
                    columns = {
                        n: (t.lower(), extra.lower())
                        for n, t, extra in cursor.fetchall()
                    }
                    source = set(
                        re.findall(
                            r"^\s*(\w+) (?:BIGINT|SMALLINT|TINYINT|VARCHAR|BOOLEAN|ENUM|TIMESTAMP|DATE|TEXT)\b",
                            ddl,
                            re.MULTILINE,
                        )
                    )
                    self.assertEqual(set(fields), source)
                    self.assertEqual(set(columns), source)
                    for name, field in fields.items():
                        self.assertEqual(
                            columns[name][0],
                            field.db_type(connection)
                            .lower()
                            .replace("integer", "int")
                            .replace("bool", "tinyint(1)")
                            .replace(", ", ","),
                        )
                    for name, col, target, target_col in re.findall(
                        r"CONSTRAINT (\w+) FOREIGN KEY \((\w+)\)\s*REFERENCES (\w+)\((\w+)\)",
                        ddl,
                    ):
                        cursor.execute(
                            "SELECT CONSTRAINT_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",
                            [table, col],
                        )
                        self.assertEqual(
                            cursor.fetchall(), ((name, target, target_col),)
                        )
                    if "ON UPDATE" in ddl:
                        self.assertIn(
                            "on update current_timestamp", columns["updated_at"][1]
                        )
            cursor.execute(
                "SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='conference_activity_indexing' AND INDEX_NAME='PRIMARY' ORDER BY SEQ_IN_INDEX"
            )
            self.assertEqual(
                [r[0] for r in cursor.fetchall()],
                ["staff_activity_id", "indexing_agency_id"],
            )
