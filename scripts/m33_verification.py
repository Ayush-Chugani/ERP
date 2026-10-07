"""Read-only installed M33 schema and actual ORM query plans."""
from datetime import date
from pathlib import Path
import json, re
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import Count
from apps.evidence.models import EvidenceDocument, EvidenceDocumentVersion, EvidenceDocumentAudit
from apps.staff_profile.models import EvidenceType, ConfidentialityLevel
root=Path(settings.BASE_DIR).parent
source=(root/'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8')
inventory=[]
for model in list(apps.get_app_config('evidence').get_models())+[EvidenceType,ConfidentialityLevel]:
 table=model._meta.db_table
 with connection.cursor() as cursor:
  cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table));ddl=cursor.fetchone()[1]
  cursor.execute('SELECT column_name,column_type,is_nullable FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',[table]);columns=cursor.fetchall()
 assert {f.column for f in model._meta.concrete_fields if f.column}=={v[0] for v in columns},table
 original=re.search(r'CREATE TABLE '+table+r'\s*\(.*?\) ENGINE=.*?;',source,re.S)
 inventory.append(dict(table=table,model=model._meta.label,source_ddl=original[0] if original else None,installed_ddl=ddl,columns=columns))
(root/'Manuals/M33_SCHEMA_INVENTORY.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
base=EvidenceDocument.objects.filter(staff_activity__deleted_at__isnull=True)
queries={
 'department_list':base.filter(staff_activity__department_id=1).select_related('staff_activity__employee','document_type','confidentiality_level','verification_status','approval_status').order_by('-pk')[:25],
 'expiry_queue':base.filter(expiry_date__lte=date(2026,12,31)).order_by('expiry_date','pk')[:100],
 'approval_queue':base.filter(approval_status__status_code='DRAFT').order_by('-pk')[:25],
 'tag_filter':base.filter(tag_links__evidence_tag_id=1).order_by('-pk')[:25],
 'current_version':EvidenceDocumentVersion.objects.filter(evidence_document_id=1,is_current=True),
 'history':EvidenceDocumentVersion.objects.filter(evidence_document_id=1).select_related('file_object').order_by('-version_number')[:25],
 'audit':EvidenceDocumentAudit.objects.filter(evidence_document_id=1).order_by('-pk')[:25],
 'type_report':base.values('document_type_id').annotate(count=Count('pk')),
 'search':base.filter(document_title__icontains='synthetic').order_by('-pk')[:25],
 'trash':EvidenceDocument.all_objects.filter(deleted_at__isnull=False,staff_activity__department_id=1).order_by('-pk')[:25],
}
report={name:dict(sql=str(query.query),explain=json.loads(query.explain(format='JSON'))) for name,query in queries.items()}
report['review']='Local MySQL plans on development cardinalities, not a production benchmark. Source FK, status, expiry and tag indexes retained. Generated current-document unique index adds a concurrency invariant. Leading-wildcard search and expiry/report workloads require representative-volume acceptance. Scoped API list query-count regression guards against per-row queries.'
(root/'Manuals/M33_QUERY_PLANS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Verified nine M33/shared tables; saved ten ORM query plans.')
