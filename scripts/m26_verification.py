"""Read-only M26 native schema and query-plan verification."""
from datetime import date
import json
import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count, Sum
from apps.funded_projects.models import FundedResearchProject, ResearchProjectFinancialUtilization
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
inventory=[]
for table in ('funded_research_project','research_project_financial_utilization'):
    match=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    model=next(m for m in apps.get_models() if m._meta.db_table==table)
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table))
        installed=cursor.fetchone()[1]
        cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table])
        columns=cursor.fetchall()
    declared={f.column for f in model._meta.concrete_fields}
    assert declared=={col[0] for col in columns},(table,declared,columns)
    inventory.append(dict(table=table,owner=model._meta.label,source_line=source[:match.start()].count('\n')+1,source_ddl=match[0],installed_ddl=installed,columns=columns,model_fields=[dict(column=f.column,field=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M26_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=FundedResearchProject.objects.filter(staff_activity__deleted_at__isnull=True)
queries={'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','funding_agency__organization','funding_type').order_by('-pk')[:25], 'sanction_range':base.filter(sanction_date__gte=date(2026,1,1)).order_by('sanction_date')[:25], 'project_period':base.filter(project_start_date__gte=date(2026,1,1),project_end_date__lte=date(2027,12,31))[:25], 'currency_report':base.values('currency_code').annotate(count=Count('pk'),sanctioned=Sum('sanctioned_amount'),received=Sum('amount_received'),utilized=Sum('amount_utilized')), 'proposal_conversion':base.filter(source_proposal_activity_id=1), 'ledger':ResearchProjectFinancialUtilization.objects.filter(staff_activity_id=1,void_record__isnull=True).order_by('reporting_period_from','pk')}
report={name:dict(sql=str(rows.query),explain=json.loads(rows.explain(format='JSON'))) for name,rows in queries.items()}
report['limitations']='Local development data only; not a production load benchmark. Native FK indexes cover PI, department, funder, type, status and project linkage. Explicit date indexes support range filtering. No speculative composite indexes added without production distribution evidence.'
(root/'Manuals/M26_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified every canonical column; wrote schema inventory and six query plans.')
