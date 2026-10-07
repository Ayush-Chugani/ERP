"""Read-only M18 discovery. Never reads business rows or changes indexes."""
import json,re
from pathlib import Path
from collections import Counter,defaultdict
import django
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader
root=Path(settings.BASE_DIR).parent
lines=[s.strip() for s in (root/'Manuals/M18_prompt_pack_extracted.txt').read_text(encoding='utf-8').splitlines() if s.strip()]
requested=[]
for i,line in enumerate(lines):
    if re.fullmatch(r'idx_[a-z0-9_]+',line):
        requested.append({'number':int(lines[i-3]),'domain':lines[i-2],'table':lines[i-1],'name':line,'columns':[s.strip() for s in lines[i+1].split(',')]})
assert len(requested)==65 and len({r['name'] for r in requested})==65
owners=defaultdict(list)
for model in apps.get_models():owners[model._meta.db_table].append(model)
with connection.cursor() as c:
    c.execute('SELECT VERSION()');server=c.fetchone()[0]
    c.execute('SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX');metadata=c.fetchall()
    c.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()');tables={r[0] for r in c.fetchall()}
indexes=defaultdict(dict)
for table,name,non_unique,column,prefix in metadata:
    item=indexes[table].setdefault(name,{'columns':[],'unique':not non_unique,'prefix_lengths':[]})
    item['columns'].append(column);item['prefix_lengths'].append(prefix)
for row in requested:
    models=owners[row['table']];row['disposition']='BLOCKED';row['reason']='No owning model'
    row['sensitive']=row['table'].startswith(('employee_','password_','login_')) or any(part in row['table'] for part in ('payment','fee_','refund','scholarship')) or row['table'] in ('user_account','file_object')
    row['existing_indexes']=indexes[row['table']]
    if len(models)!=1:
        row['reason']='Ambiguous owners' if models else 'Module/model not implemented';continue
    model=models[0];columns={f.column:f.name for f in model._meta.local_fields}
    row.update(app=model._meta.app_label,model=model._meta.object_name,managed=model._meta.managed,django_fields=[columns.get(c) for c in row['columns']])
    if not model._meta.managed:row['reason']='Unmanaged owner requires a reviewed state/database strategy';continue
    if any(c not in columns for c in row['columns']):row['reason']='Missing physical column mapping';continue
    if row['table'] not in tables:row['reason']='Owning model migration not yet applied';continue
    if len(row['name'])>64:row['reason']='Exceeds MySQL/MariaDB identifier limit';continue
    same=indexes[row['table']].get(row['name'])
    row['exact_equivalents']=[n for n,v in indexes[row['table']].items() if v['columns']==row['columns'] and not any(v['prefix_lengths'])]
    row['leftmost_candidates']=[n for n,v in indexes[row['table']].items() if len(v['columns'])>len(row['columns']) and v['columns'][:len(row['columns'])]==row['columns'] and not any(v['prefix_lengths'])]
    if same and same['columns']==row['columns'] and not any(same['prefix_lengths']):
        row.update(disposition='ALREADY_COVERED',reason='Exact requested name and ordered columns exist')
    elif same:row.update(disposition='BLOCKED',reason='Requested index name exists with a different definition')
    elif row['exact_equivalents']:row.update(disposition='NEEDS_REVIEW',reason='Exact columns already indexed under another name; decide duplicate versus documented waiver')
    elif len(row['name'])>30:row.update(disposition='NEEDS_REVIEW',reason='Database permits the name, but Django Index portable name limit is 30; preserve exact name with reviewed backend-specific index class')
    else:row.update(disposition='ADD',reason='Candidate only; await prior modules and workload/deployment review')
loader=MigrationLoader(connection)
report={'stage':'Read-only discovery; no M18 index implementation','django_version':django.get_version(),'database_version':server,'backend':connection.vendor,'auth_user_model':settings.AUTH_USER_MODEL,'routers':getattr(settings,'DATABASE_ROUTERS',[]),'migration_heads':loader.graph.leaf_nodes(),'counts':dict(Counter(r['disposition'] for r in requested)),'indexes':requested}
(root/'Manuals/M18_DISCOVERY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'count':len(requested),'counts':report['counts'],'database_version':server,'blocked_tables':sorted({r['table'] for r in requested if r['disposition']=='BLOCKED'})},indent=2))
