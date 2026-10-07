"""Validate proposed DDL in a uniquely named disposable MySQL database.

Copies table definitions only. No production rows are read or changed.
The disposable database is removed in finally, including after a failed probe.
"""
import os
import re
from pathlib import Path
from uuid import uuid4

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.db import connection

name = 'test_sims_m7_schema_probe_' + uuid4().hex
assert re.fullmatch(r'test_sims_m7_schema_probe_[a-f0-9]{32}', name)
probe = connection.copy(alias='m7_schema_probe')
probe.settings_dict = {**connection.settings_dict, 'NAME': name}
created = False
try:
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if 'programme_term_offering' in tables:
            raise RuntimeError('M7 tables already exist; use a migration adoption test instead.')
        definitions = []
        for table in tables:
            cursor.execute('SHOW CREATE TABLE ' + connection.ops.quote_name(table))
            definitions.append(cursor.fetchone()[1])
        cursor.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        created = True
    with probe.cursor() as cursor:
        cursor.execute('SET FOREIGN_KEY_CHECKS=0')
        try:
            for definition in definitions:
                cursor.execute(definition)
        finally:
            cursor.execute('SET FOREIGN_KEY_CHECKS=1')
        sql = Path('Manuals/M7_REVISED_SCHEMA_PROPOSAL.sql').read_text(encoding='utf-8')
        sql = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
        statements = [statement.strip() for statement in sql.split(';') if statement.strip()]
        for statement in statements:
            cursor.execute(statement)
        cursor.execute('SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=%s AND CONSTRAINT_NAME LIKE %s', [name, 'fk_m7_%'])
        fk_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s', [name])
        assert cursor.fetchone()[0] == len(tables) + 8
        assert fk_count == 23, fk_count
    print(f'PASS: {len(statements)} DDL statements; eight M7 tables; {fk_count} additional foreign keys.')
finally:
    probe.close()
    if created:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{name}`')
        print('Disposable schema removed; application database unchanged.')
