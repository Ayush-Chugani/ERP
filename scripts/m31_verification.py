"""Read-only schema fidelity and actual ORM query-plan evidence for M31."""
from datetime import date
from pathlib import Path
import json,re
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count
from apps.professional_memberships.models import StaffProfessionalMembership
from apps.staff_profile.models import MembershipType
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
models=list(apps.get_app_config('professional_memberships').get_models())+[MembershipType]
inventory=[]
for model in models:
    table=model._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));ddl=cursor.fetchone()[1]
        cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table]);columns=cursor.fetchall()
    assert {f.column for f in model._meta.concrete_fields}=={v[0] for v in columns},table
    original=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
    inventory.append(dict(table=table,model=model._meta.label,source_ddl=original[0] if original else None,source_line=source[:original.start()].count('\n')+1 if original else None,installed_ddl=ddl,columns=columns,fields=[dict(column=f.column,name=f.name,type=f.db_type(connection)) for f in model._meta.concrete_fields]))
(root/'Manuals/M31_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=StaffProfessionalMembership.objects.filter(staff_activity__deleted_at__isnull=True)
queries={
 'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','staff_activity__department','organization','membership_type','role_type','participation_level').order_by('-pk')[:25],
 'organization_number':base.filter(organization_id=1,membership_number='SYNTHETIC').order_by('-pk')[:25],
 'membership_type':base.filter(membership_type_id=1).order_by('-pk')[:25],
 'expiry_candidates':base.filter(membership_status='ACTIVE',is_lifetime_membership=False,membership_expiry_date__lt=date(2026,9,28)).order_by('pk')[:100],
 'renewal_due':base.filter(membership_status='ACTIVE',is_lifetime_membership=False,renewal_required=True,membership_expiry_date__range=(date(2026,9,28),date(2026,10,28))).order_by('-pk')[:25],
 'status_report':base.values('membership_status').annotate(count=Count('pk')),
 'text_search':base.filter(membership_number__icontains='synthetic').order_by('-pk')[:25],
 'organization_report':base.values('organization__organization_name').annotate(count=Count('pk')),
}
report={name:dict(sql=str(query.query),explain=json.loads(query.explain(format='JSON'))) for name,query in queries.items()}
report['review']='Local MySQL EXPLAIN evidence, not a volume benchmark. Native FK indexes and unique (organization_id,membership_number) are retained. For measured large-scale expiry workloads, evaluate (membership_status,is_lifetime_membership,membership_expiry_date,staff_activity_id); for renewal workloads include renewal_required if selectivity warrants it. No speculative source indexes or duplicate FK indexes added. Leading-wildcard searches require representative-volume acceptance. Query-count tests enforce constant list query count.'
(root/'Manuals/M31_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified source, type and history tables; saved eight ORM query plans.')
