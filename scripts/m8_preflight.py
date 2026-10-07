"""Inspect M8 dependencies without reading personal data or changing the database."""
import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.db import connection

owned = 'faculty_course_assignment timetable_session'.split()
parents = 'employee employee_assignment employee_competency course_offering_section course_offering programme_term_offering class_section class_batch room time_slot academic_term user_account'.split()
lines = ['# M8 dependency inspection', '', 'Read-only; no personal records inspected.', '']
with connection.cursor() as cursor:
    cursor.execute('SELECT VERSION()')
    lines.append('MySQL: ' + cursor.fetchone()[0])
    tables = set(connection.introspection.table_names(cursor))
    lines += ['', '## M8 tables', *[f'- {name}: ' + ('exists; adoption review required' if name in tables else 'absent') for name in owned]]
    for name in parents:
        lines += ['', '## ' + name]
        if name not in tables:
            lines.append('MISSING')
            continue
        cursor.execute('SHOW CREATE TABLE ' + connection.ops.quote_name(name))
        lines += ['```sql', cursor.fetchone()[1], '```']
Path('Manuals/M8_UPSTREAM_SCHEMA.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('Saved M8 dependency inspection. Existing M8 tables:', sum(name in tables for name in owned))
