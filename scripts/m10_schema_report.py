from pathlib import Path
from django.db import connection
from django.conf import settings
TABLES=['assessment_component','assessment_event','student_assessment_mark','grade_scale','grade_rule','student_course_result','student_term_result']
parts=['# M10 local schema and query plans', 'Database: '+settings.DATABASES['default']['NAME']]
with connection.cursor() as cursor:
    for table in TABLES:
        cursor.execute('SHOW CREATE TABLE '+table);parts.extend(['## '+table,'```sql',cursor.fetchone()[1],'```'])
    for sql in ['SELECT * FROM assessment_event WHERE course_offering_id=1 AND status=\'CONDUCTED\' ORDER BY assessment_date','SELECT * FROM student_assessment_mark WHERE assessment_event_id=1','SELECT * FROM student_course_result WHERE course_registration_id=1 ORDER BY attempt_number','SELECT * FROM student_term_result WHERE term_registration_id=1']:
        cursor.execute('EXPLAIN '+sql);parts.extend(['## Query','```sql',sql,'```','```',str(cursor.fetchall()),'```'])
parts.append('Plans reflect the local empty development database, not production cardinality or latency acceptance.')
Path('Manuals/M10_SCHEMA_AND_QUERY_PLANS.md').write_text('\n\n'.join(parts),encoding='utf-8')
