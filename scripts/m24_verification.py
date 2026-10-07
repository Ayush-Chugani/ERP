"""Read-only native mapping and representative MySQL query-plan evidence."""
import json
import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count
from apps.faculty_internships.models import FacultyInternship
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
inventory=[]
for table in ('industry_sector','faculty_internship'):
    match=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    model=next(m for m in apps.get_models() if m._meta.db_table==table)
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table))
        installed=cursor.fetchone()[1]
    inventory.append(dict(table=table,owner=model._meta.label,source_line=source[:match.start()].count('\n')+1,source_ddl=match[0],installed_ddl=installed,columns=[dict(column=f.column,field=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M24_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=FacultyInternship.objects.filter(staff_activity__deleted_at__isnull=True)
queries={'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','organization','industry_sector').order_by('-pk')[:25], 'organization_search':base.filter(organization__organization_name__icontains='synthetic').order_by('-pk')[:25], 'currency_report':base.filter(staff_activity__institution_id=1).values('currency_code').annotate(count=Count('pk'))}
report={name:dict(sql=str(rows.query),explain=json.loads(rows.explain(format='JSON'))) for name,rows in queries.items()}
report['limitations']='Local development distribution, not a production load benchmark. No speculative indexes added; source PK/FK indexes retained.'
(root/'Manuals/M24_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Wrote M24 native schema inventory and three read-only query plans.')
