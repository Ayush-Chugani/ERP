"""Frozen install: exact DDL, no silent adoption or destructive data reversal."""

import re

from ._industry_ddl import DDL


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        raise RuntimeError("This source-schema migration requires MySQL/MariaDB.")
    tables = [re.search(r"CREATE TABLE (\w+)", ddl)[1] for ddl in DDL]
    existing = set(schema_editor.connection.introspection.table_names())
    overlap = existing.intersection(tables)
    if overlap:
        raise RuntimeError(
            "Existing tables require explicit schema adoption review: "
            + ", ".join(sorted(overlap))
        )
    for ddl in DDL:
        schema_editor.execute(ddl)


def uninstall(apps, schema_editor):
    tables = [re.search(r"CREATE TABLE (\w+)", ddl)[1] for ddl in DDL]
    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                "SELECT 1 FROM " + schema_editor.quote_name(table) + " LIMIT 1"
            )
            if cursor.fetchone():
                raise RuntimeError(
                    "Refusing to reverse populated staff research tables."
                )
        for table in reversed(tables):
            schema_editor.execute("DROP TABLE " + schema_editor.quote_name(table))
