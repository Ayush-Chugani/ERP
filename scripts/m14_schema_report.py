from pathlib import Path
from django.db import connection
from apps.communication import models as m
parts=['# M14 schema and local query plans','Baseline tables plus explicitly approved institution ownership and programme/user targets. These local empty-table plans do not establish production performance.']
with connection.cursor() as cursor:
    for model in [m.AnnouncementType,m.Announcement,m.AnnouncementAttachment,m.ProgrammeTarget,m.UserTarget]:
        table=model._meta.db_table
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table))
        parts += ['## '+table,'```sql',cursor.fetchone()[1],'```']
    for sql in ["SELECT announcement_id FROM announcement WHERE institution_id=1 AND approval_status='APPROVED' AND publish_from<=UTC_TIMESTAMP() AND (publish_to IS NULL OR publish_to>UTC_TIMESTAMP()) ORDER BY publish_from DESC,announcement_id DESC LIMIT 50", "SELECT * FROM announcement_programme_target WHERE programme_id=1", "SELECT * FROM announcement_user_target WHERE user_id=1"]:
        cursor.execute('EXPLAIN '+sql)
        parts+=['```sql',sql,'```','```',str(cursor.fetchall()),'```']
Path('Manuals/M14_SCHEMA_AND_QUERY_PLANS.md').write_text('\n\n'.join(parts),encoding='utf-8')
