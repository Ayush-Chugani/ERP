from pathlib import Path
from django.db import connection
from django.conf import settings
from apps.feedback import models
parts=['# M11 local schema and query plans','Database: '+settings.DATABASES['default']['NAME']]
with connection.cursor() as cursor:
    for model in [models.Category,models.Question,models.Choice,models.Questionnaire,models.QuestionnaireItem,models.Cycle,models.Response,models.ResponseItem,models.ResponseItemChoice,models.SubmissionLedger,models.Audit,models.CommandReceipt]:
        table=model._meta.db_table
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));parts.extend(['## '+table,'```sql',cursor.fetchone()[1],'```'])
    for sql in ["SELECT * FROM feedback_cycle WHERE academic_term_id=1 AND status='OPEN' AND start_at<=NOW() AND end_at>NOW()", "SELECT * FROM feedback_response WHERE feedback_cycle_id=1 AND target_key='course:1'", "SELECT * FROM feedback_response_item WHERE feedback_response_id=1"]:
        cursor.execute('EXPLAIN '+sql);parts.extend(['## Query','```sql',sql,'```','```',str(cursor.fetchall()),'```'])
parts.append('Empty development database plans do not establish populated load performance or production latency.')
Path('Manuals/M11_SCHEMA_AND_QUERY_PLANS.md').write_text('\n\n'.join(parts),encoding='utf-8')
