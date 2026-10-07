"""Read-only schema fidelity and actual ORM query-plan evidence for M32."""
from datetime import date
from pathlib import Path
import json,re
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count
from apps.professional_contributions.models import StaffProfessionalContribution
from apps.staff_profile.models import ProfessionalContributionType
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
models=list(apps.get_app_config('professional_contributions').get_models())+[ProfessionalContributionType]
inventory=[]
for model in models:
    table=model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));ddl=cursor.fetchone()[1]
        cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table]);columns=cursor.fetchall()
    assert {f.column for f in model._meta.concrete_fields}=={v[0] for v in columns},table
    original=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    inventory.append(dict(table=table,model=model._meta.label,source_ddl=original[0] if original else None,source_line=source[:original.start()].count('\n')+1 if original else None,installed_ddl=ddl,columns=columns,fields=[dict(column=f.column,name=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M32_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=StaffProfessionalContribution.objects.filter(staff_activity__deleted_at__isnull=True)
queries={
 'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','staff_activity__department','professional_contribution_type','organization','journal','conference_event','programme','course','student').order_by('-pk')[:25],
 'type_date':base.filter(professional_contribution_type_id=1,contribution_date__range=(date(2026,1,1),date(2026,12,31))).order_by('-contribution_date','-pk')[:25],
 'journal_context':base.filter(journal_id=1).order_by('-pk')[:25],
 'student_context':base.filter(student_id=1).order_by('-pk')[:25],
 'duplicate_candidates':base.filter(staff_activity__employee_id=1,professional_contribution_type_id=1,title_topic='Synthetic',contribution_date=date(2026,1,1)).order_by('-pk')[:5],
 'type_report':base.values('professional_contribution_type_id').annotate(count=Count('pk')),
 'text_search':base.filter(title_topic__icontains='synthetic').order_by('-pk')[:25],
 'organization_report':base.values('organization_id').annotate(count=Count('pk')),
}
report={name:dict(sql=str(query.query),explain=json.loads(query.explain(format='JSON'))) for name,query in queries.items()}
report['review']='Local MySQL EXPLAIN evidence, not a representative-volume benchmark. Native FK indexes are retained. The consolidated SQL suggests (professional_contribution_type_id, contribution_date); evaluate that composite against measured type/date workloads before adding it. No speculative or duplicate indexes were added. Leading-wildcard title/reference searches need production-volume acceptance. Query-count tests cover lists with all six contexts.' 
(root/'Manuals/M32_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified source, type and history tables; saved eight ORM query plans.')
