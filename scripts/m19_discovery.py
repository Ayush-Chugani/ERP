"""Read-only M19 schema discovery; never reads business records."""
import json
import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.db import connection

root = Path(settings.BASE_DIR).parent
pack = (root / 'Manuals/M19_prompt_pack_extracted.txt').read_text(encoding='utf-8')
source = (root / 'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
tables = re.findall(r'^\d{2}\s+([a-z_]+)\s*$', pack, re.M)
assert len(tables) == len(set(tables)) == 28
with connection.cursor() as cursor:
    cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
    installed = {row[0] for row in cursor.fetchall()}
rows = []
for table in tables:
    matches = list(re.finditer(r'CREATE TABLE ' + re.escape(table) + r'\s*\(.*?\) ENGINE=.*?;', source, re.S))
    if len(matches) != 1:
        raise RuntimeError('Expected one source definition: ' + table)
    match = matches[0]
    owners = [m._meta.label for m in apps.get_models() if m._meta.db_table == table]
    rows.append(dict(table=table, source_line=source[:match.start()].count('\n') + 1,
                     owners=owners, installed=table in installed,
                     references=re.findall(r'REFERENCES\s+(\w+)', match[0]), ddl=match[0],
                     disposition='REVIEW_EXISTING' if owners or table in installed else 'CREATE_AFTER_PREDECESSORS'))
report = dict(stage='Preliminary read-only discovery; implementation queued after M18',
              auth_user_model=settings.AUTH_USER_MODEL, tables=rows)
(root / 'Manuals/M19_SCHEMA_INVENTORY.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(dict(tables=len(rows), existing=[r['table'] for r in rows if r['installed']],
                     owned=[r['table'] for r in rows if r['owners']]), indent=2))
