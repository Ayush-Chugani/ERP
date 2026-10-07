"""Read-only schema fidelity and actual ORM query-plan evidence for M27."""
from datetime import date
from pathlib import Path
import json,re
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count,Sum
from apps.consultancy.models import ConsultancyProject,ProjectReceipt,ProjectMilestone
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
models=list(apps.get_app_config('consultancy').get_models())
inventory=[]
for model in models:
    table=model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));ddl=cursor.fetchone()[1]
        cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table]);columns=cursor.fetchall()
    assert {f.column for f in model._meta.concrete_fields}=={v[0] for v in columns},table
    original=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    inventory.append(dict(table=table,model=model._meta.label,source_ddl=original[0] if original else None,source_line=source[:original.start()].count('\n')+1 if original else None,installed_ddl=ddl,columns=columns,fields=[dict(column=f.column,name=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M27_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=ConsultancyProject.objects.filter(staff_activity__deleted_at__isnull=True)
queries={'department_list':base.filter(staff_activity__department_id=1).select_related('client_organization','principal_consultant_employee','staff_activity__department').order_by('-pk')[:25],'client_list':base.filter(client_organization_id=1).order_by('-pk')[:25],'status_date':base.filter(status='ONGOING',project_start_date__gte=date(2026,1,1)).order_by('project_start_date')[:25],'client_search':base.filter(client_organization__organization_name__icontains='synthetic')[:25],'currency_totals':base.values('currency_code').annotate(count=Count('pk'),value=Sum('consultancy_amount'),received=Sum('amount_received')),'receipts':ProjectReceipt.objects.filter(project_id=1,void_record__isnull=True).order_by('pk'),'milestone_overdue':ProjectMilestone.objects.filter(project_id=1,status='PLANNED',due_date__lt=date(2026,9,26))}
report={name:dict(sql=str(query.query),explain=json.loads(query.explain(format='JSON'))) for name,query in queries.items()}
report['review']='Local development plans, not a production benchmark. Existing client/principal/project FK indexes and receipt/membership/sequence unique indexes are retained. No redundant FK indexes added. Status/type/date composite indexes need representative institutional distribution and slow-query evidence before adding an explicit migration; leading-wildcard text search cannot benefit from ordinary name B-tree indexes. List query-count regression checks constant queries as row counts grow.'
(root/'Manuals/M27_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified core and five approved extension tables; saved seven query plans.')
