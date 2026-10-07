"""Inspect M7 dependencies without reading personal data or changing the database."""
import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.db import connection

owned = '''programme_term_offering class_section class_batch student_term_registration
course_offering course_offering_section student_course_registration course_offering_section_student'''.split()
parents = '''academic_term programme programme_specialization curriculum_scheme curriculum_course
semester room course_catalog student_programme_enrolment user_account'''.split()
lines = ['# M7 dependency inspection', '', 'Read-only; no personal records inspected.', '']
with connection.cursor() as cursor:
    cursor.execute('SELECT VERSION()')
    lines.append('MySQL: ' + cursor.fetchone()[0])
    tables = set(connection.introspection.table_names(cursor))
    lines += ['', '## M7 tables', *[f'- {name}: ' + ('exists; adoption review required' if name in tables else 'absent') for name in owned]]
    for name in parents:
        lines += ['', '## ' + name]
        if name not in tables:
            lines.append('MISSING')
            continue
        cursor.execute('SHOW CREATE TABLE ' + connection.ops.quote_name(name))
        lines += ['```sql', cursor.fetchone()[1], '```']
Path('Manuals/M7_UPSTREAM_SCHEMA.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('Saved M7 dependency inspection. Existing M7 tables:', sum(name in tables for name in owned))
