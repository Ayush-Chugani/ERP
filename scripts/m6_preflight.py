"""Read-only M6 dependency inspection; no personal data or secrets."""
import os
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.db import connection
owned='admission_applicant admission_application student_programme_enrolment enrolment_status_history'.split()
parents='student programme programme_specialization curriculum_scheme semester academic_year admission_category gender country social_category caste sub_caste user_account institution campus department'.split()
lines=['# M6 live schema inspection','','Read-only; no personal records inspected.','']
with connection.cursor() as cursor:
    cursor.execute('SELECT VERSION()');lines.append('MySQL: '+cursor.fetchone()[0])
    existing=set(connection.introspection.table_names(cursor))
    lines += ['', '## Module6 target tables', *[f'- {name}: '+('exists; adoption review required' if name in existing else 'absent') for name in owned]]
    for name in parents:
        lines += ['', '## '+name]
        if name not in existing:lines.append('MISSING');continue
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(name));lines += ['```sql',cursor.fetchone()[1],'```']
Path('Manuals/M6_UPSTREAM_SCHEMA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Saved M6 upstream DDL. Existing M6 target tables:',sum(name in existing for name in owned))
