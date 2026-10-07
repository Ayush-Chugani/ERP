"""Read-only M22 dependency discovery. Inspects schema metadata, not business rows."""
import json
import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.db import connection

root = Path(settings.BASE_DIR).parent
source = (root / 'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
requested = ('conference_event', 'conference_activity', 'conference_activity_indexing')
definitions = {}
for match in re.finditer(r'CREATE TABLE (\w+)\s*\(.*?\) ENGINE=.*?;', source, re.S):
    definitions.setdefault(match[1], []).append(match)
with connection.cursor() as cursor:
    cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
    installed = {row[0] for row in cursor.fetchall()}


def describe(table):
    matches = definitions.get(table, [])
    if len(matches) != 1:
        raise RuntimeError('Expected one source table definition: ' + table)
    match = matches[0]
    return dict(table=table, source_line=source[:match.start()].count('\n') + 1,
                owners=[m._meta.label for m in apps.get_models() if m._meta.db_table == table],
                installed=table in installed,
                references=sorted(set(re.findall(r'REFERENCES\s+(\w+)', match[0]))), ddl=match[0])


tables = [describe(table) for table in requested]
dependencies = sorted(set(ref for row in tables for ref in row['references']) - set(requested))
# Staff activity has its own upstream dependencies, not just the conference masters.
dependencies = sorted(set(dependencies) | set(describe('staff_activity')['references']))
upstream = [describe(table) for table in dependencies]
report = dict(stage='Schema/model discovery; consult M22_IMPLEMENTATION.md for implemented scope', tables=tables,
              dependencies=upstream,
              unresolved=[row['table'] for row in upstream if not row['owners'] or not row['installed']])
(root / 'Manuals/M22_SCHEMA_INVENTORY.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(dict(requested_tables=len(tables), existing=[r['table'] for r in tables if r['installed']],
                     owners={r['table']: r['owners'] for r in upstream}, unresolved=report['unresolved']), indent=2))
