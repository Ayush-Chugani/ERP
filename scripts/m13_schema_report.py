from pathlib import Path
import re
from django.db import connection
from apps.documents_exit.migrations._canonical import DDL,verify
parts=['# M13 canonical schema and local query plans','Verified against the supplied DDL; native TIMESTAMP/ENUM/check/unique/FK semantics are preserved.']
with connection.cursor() as cursor:
    for sql in DDL:
        table=re.search(r'CREATE TABLE (\w+)',sql)[1];verify(cursor,sql)
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));parts += ['## '+table,'```sql',cursor.fetchone()[1],'```']
    for sql in ["SELECT student_document_id,verification_status FROM student_document WHERE student_id=1", "SELECT certificate_request_id,request_status FROM certificate_request WHERE student_id=1 AND request_status='APPROVED'", "SELECT * FROM student_exit WHERE enrolment_id=1"]:
        cursor.execute('EXPLAIN '+sql);parts += ['```sql',sql,'```','```',str(cursor.fetchall()),'```']
parts += ['Plans describe the local development database only; populated load and storage throughput require separate acceptance.']
Path('Manuals/M13_SCHEMA_AND_QUERY_PLANS.md').write_text('\n\n'.join(parts),encoding='utf-8')
