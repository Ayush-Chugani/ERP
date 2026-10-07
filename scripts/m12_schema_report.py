from pathlib import Path
import re
from django.db import connection
from apps.student_support import models
from apps.student_support.migrations._canonical import DDL,verify
parts=['# M12 schema fidelity and local query plans','Canonical DDL is frozen in the initial migration. No extra domain columns or indexes are created.']
with connection.cursor() as cursor:
    for sql in DDL:
        table=re.search(r'CREATE TABLE (\w+)',sql)[1]
        verify(cursor,sql)
        model=next(model for model in [models.MentorAssignment,models.CounsellingSession,models.GrievanceCategory,models.Grievance,models.GrievanceAction] if model._meta.db_table==table)
        parts += ['## '+table,'| Column | Django field | Nullable | Default | Choices | Relationship |','| --- | --- | --- | --- | --- | --- |']
        for field in model._meta.fields:
            default=field.default if field.has_default() else str(field.db_default) if field.has_db_default() else 'none'
            target=field.related_model._meta.db_table if field.is_relation else ''
            parts += ['| '+' | '.join([field.column,field.__class__.__name__,str(field.null),str(default),str([v for v,_ in field.choices]) if field.choices else '',target])+' |']
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));parts += ['```sql',cursor.fetchone()[1],'```']
    for sql in ["SELECT * FROM mentor_assignment WHERE student_id=1 AND assignment_status='ACTIVE'", "SELECT counselling_session_id,session_date,session_status FROM counselling_session WHERE mentor_assignment_id=1 ORDER BY session_date", "SELECT grievance_id,status,submitted_at FROM grievance WHERE department_id=1 AND status='SUBMITTED' ORDER BY submitted_at", "SELECT * FROM grievance_action WHERE grievance_id=1 ORDER BY action_at,grievance_action_id"]:
        cursor.execute('EXPLAIN '+sql);parts += ['```sql',sql,'```','```',str(cursor.fetchall()),'```']
parts += ['These plans describe the local development database only. Canonical foreign-key indexes are retained. Status/date composite indexes require a separately reviewed schema change and are deliberately not added.']
Path('Manuals/M12_SCHEMA_AND_QUERY_PLANS.md').write_text('\n\n'.join(parts),encoding='utf-8')
