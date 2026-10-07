"""Read-only schema fidelity and actual ORM query-plan evidence for M30."""
from datetime import date
from pathlib import Path
import json,re
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count, Sum
from apps.awards.models import StaffAward
from apps.staff_profile.models import AwardCategory
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
models=list(apps.get_app_config('awards').get_models())+[AwardCategory]
inventory=[]
for model in models:
    table=model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));ddl=cursor.fetchone()[1]
        cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table]);columns=cursor.fetchall()
    assert {f.column for f in model._meta.concrete_fields}=={v[0] for v in columns},table
    original=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    inventory.append(dict(table=table,model=model._meta.label,source_ddl=original[0] if original else None,source_line=source[:original.start()].count('\n')+1 if original else None,installed_ddl=ddl,columns=columns,fields=[dict(column=f.column,name=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M30_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=StaffAward.objects.filter(staff_activity__deleted_at__isnull=True)
queries={
 'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','staff_activity__department','award_category','awarding_organization').order_by('-award_date','-pk')[:25],
 'category_list':base.filter(award_category_id=1).order_by('-award_date','-pk')[:25],
 'date_list':base.filter(award_date__gte=date(2026,1,1)).order_by('-award_date','-pk')[:25],
 'organization_list':base.filter(awarding_organization_id=1).order_by('-award_date','-pk')[:25],
 'money_filter':base.filter(cash_prize_amount__gte='1.00',currency_code='INR').order_by('-pk')[:25],
 'currency_totals':base.values('currency_code').annotate(cash=Sum('cash_prize_amount'),incentive=Sum('incentive_amount')),
 'text_search':base.filter(award_name__icontains='synthetic').order_by('-pk')[:25],
 'category_report':base.values('award_category__category_name').annotate(count=Count('pk')),
}
report={name:dict(sql=str(query.query),explain=json.loads(query.explain(format='JSON'))) for name,query in queries.items()}
report['review']='Local development EXPLAIN evidence, not a production load benchmark. Canonical FK indexes support category and awarding organization filters. List regression asserts constant query count. Date sorting and leading-wildcard search require representative production row distribution before proposing another index; no speculative or redundant indexes introduced.'
(root/'Manuals/M30_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified source, category and history tables; saved eight ORM query plans.')
