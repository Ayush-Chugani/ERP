from django.db import migrations

def finalize_contract(apps, schema_editor):
    import re
    from ._restricted_ddl import DDL
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for ddl in DDL:
            table = re.search(r'CREATE TABLE (\w+)', ddl)[1]
            cursor.execute('ALTER TABLE ' + quote(table) + ' DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci, MODIFY updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')
            for wanted, column, target, target_column in re.findall(r'CONSTRAINT (\w+) FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)', ddl):
                cursor.execute('SELECT CONSTRAINT_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL', [table, column])
                matches = cursor.fetchall()
                if len(matches) != 1 or tuple(matches[0][1:]) != (target, target_column):
                    raise RuntimeError('M16 restricted FK contract mismatch: ' + table + '.' + column)
                actual = matches[0][0]
                if actual != wanted:
                    cursor.execute('ALTER TABLE ' + quote(table) + ' DROP FOREIGN KEY ' + quote(actual) + ', ADD CONSTRAINT ' + quote(wanted) + ' FOREIGN KEY (' + quote(column) + ') REFERENCES ' + quote(target) + ' (' + quote(target_column) + ')')

class Migration(migrations.Migration):
    atomic = False
    dependencies = [('employee_hr', '0004_restricted_records')]
    operations = [migrations.RunPython(finalize_contract)]
