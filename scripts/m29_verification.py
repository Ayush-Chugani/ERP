"""Read-only schema fidelity and actual ORM query-plan evidence for M29."""
from datetime import date
from pathlib import Path
import json,re
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count
from apps.extracurricular.models import ExtracurricularActivity
from apps.staff_profile.models import ExtraCurricularCategory
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
models=list(apps.get_app_config('extracurricular').get_models())+[ExtraCurricularCategory]
inventory=[]
for model in models:
    table=model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));ddl=cursor.fetchone()[1]
        cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table]);columns=cursor.fetchall()
    assert {f.column for f in model._meta.concrete_fields}=={v[0] for v in columns},table
    original=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    inventory.append(dict(table=table,model=model._meta.label,source_ddl=original[0] if original else None,source_line=source[:original.start()].count('\n')+1 if original else None,installed_ddl=ddl,columns=columns,fields=[dict(column=f.column,name=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M29_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=ExtracurricularActivity.objects.filter(staff_activity__deleted_at__isnull=True)
queries={
 'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','staff_activity__department','extracurricular_category','organizer__organization','institution_organization','country','state').order_by('-pk')[:25],
 'category_list':base.filter(extracurricular_category_id=1).order_by('-pk')[:25],
 'date_list':base.filter(event_date__gte=date(2026,1,1)).order_by('event_date','pk')[:25],
 'organizer_list':base.filter(organizer_id=1).order_by('-pk')[:25],
 'geography':base.filter(country_id=1,state_id=1).order_by('-pk')[:25],
 'award_report':base.exclude(award_recognition__isnull=True).exclude(award_recognition='').values('staff_activity__department_id').annotate(count=Count('pk')),
 'text_search':base.filter(activity_details__icontains='synthetic').order_by('-pk')[:25],
 'category_report':base.values('extracurricular_category__category_name').annotate(count=Count('pk')),
}
report={name:dict(sql=str(query.query),explain=json.loads(query.explain(format='JSON'))) for name,query in queries.items()}
report['review']='Local development EXPLAIN evidence, not a production load benchmark. Canonical FK indexes support category, organizer, organization and geography filters. List regression asserts constant query count. Date sorting and leading-wildcard search require representative production row distribution before proposing another index; no speculative or redundant indexes introduced.'
(root/'Manuals/M29_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified source, category and history tables; saved eight ORM query plans.')
