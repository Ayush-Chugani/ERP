"""Read-only M5 schema preflight; no records or credentials are printed."""
import os
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.db import connection
owned = 'student student_address student_parent_guardian student_residence student_previous_education student_entrance_exam staff_type staff_category employment_source external_agency designation employee employee_address employee_assignment employee_competency'.split()
parents = 'country state gender blood_group religion social_category caste sub_caste institution campus department course_catalog user_account'.split()
lines = ['# M5 live schema preflight', '', 'Read-only inspection; no personal records or credentials are collected.', '']
with connection.cursor() as cursor:
    cursor.execute('SELECT VERSION()')
    lines.append('Database version: ' + cursor.fetchone()[0])
    present = set(connection.introspection.table_names(cursor))
    lines += ['', '## Target tables', '', *[f'- {name}: {"EXISTS: adoption review required" if name in present else "absent"}' for name in owned]]
    for name in parents:
        lines += ['', '## ' + name]
        if name not in present:
            lines.append('MISSING')
            continue
        cursor.execute('SHOW CREATE TABLE ' + connection.ops.quote_name(name))
        lines += ['```sql', cursor.fetchone()[1], '```']
Path('Manuals/M5_UPSTREAM_SCHEMA.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('Read-only M5 preflight saved. Existing target tables:', sum(name in present for name in owned))
