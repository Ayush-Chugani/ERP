"""Preserve the source's named history-owner foreign-key contracts."""
import re
from django.db import migrations
from ._history_ddl import DDL


def align(apps,schema_editor):
    quote=schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for sql in DDL:
            table=re.search(r'CREATE TABLE (\w+)',sql)[1]
            for wanted,column,target,target_column in re.findall(r'CONSTRAINT (\w+) FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)',sql):
                cursor.execute('SELECT CONSTRAINT_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL',[table,column])
                matches=cursor.fetchall()
                if len(matches)!=1 or tuple(matches[0][1:])!=(target,target_column):
                    raise RuntimeError('M16 history FK contract mismatch: '+table+'.'+column)
                actual=matches[0][0]
                if actual!=wanted:
                    cursor.execute('ALTER TABLE '+quote(table)+' DROP FOREIGN KEY '+quote(actual)+', ADD CONSTRAINT '+quote(wanted)+' FOREIGN KEY ('+quote(column)+') REFERENCES '+quote(target)+' ('+quote(target_column)+')')

class Migration(migrations.Migration):
    atomic=False
    dependencies=[('employee_hr','0002_education_and_employment')]
    operations=[migrations.RunPython(align)]
