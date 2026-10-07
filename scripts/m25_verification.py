"""Read-only native mapping and representative MySQL query-plan evidence."""
from datetime import date
import json
import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count
from apps.research_proposals.models import ResearchProposal
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
inventory=[]
for table in ('funding_type','funding_agency','research_status','research_proposal'):
    match=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    model=next(m for m in apps.get_models() if m._meta.db_table==table)
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table))
        installed=cursor.fetchone()[1]
    inventory.append(dict(table=table,owner=model._meta.label,source_line=source[:match.start()].count('\n')+1,source_ddl=match[0],installed_ddl=installed,columns=[dict(column=f.column,field=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M25_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=ResearchProposal.objects.filter(staff_activity__deleted_at__isnull=True)
queries={'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','funding_agency__organization','funding_type').order_by('-pk')[:25], 'organization_search':base.filter(funding_agency__organization__organization_name__icontains='synthetic').order_by('-pk')[:25], 'currency_report':base.filter(staff_activity__institution_id=1).values('currency_code').annotate(count=Count('pk'))}
queries.update({'pi_list':base.filter(principal_investigator_employee_id=1).order_by('-pk')[:25], 'status_list':base.filter(research_status_id=1).order_by('-pk')[:25], 'submission_range':base.filter(proposal_submission_date__gte=date(2026,1,1)).order_by('proposal_submission_date','pk')[:25]})
report={name:dict(sql=str(rows.query),explain=json.loads(rows.explain(format='JSON'))) for name,rows in queries.items()}
report['limitations']='Local development distribution, not a production load benchmark. No speculative indexes added; source PK/FK indexes retained.'
(root/'Manuals/M25_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Wrote M25 native schema inventory and six read-only query plans.')
