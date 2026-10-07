"""Read-only M15 cutover inventory. Run through manage.py shell.

Outputs schema metadata and aggregate counts only; never user identifiers,
password material, session IDs, tokens or individual audit records.
"""
import json
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.db.models.functions import Length
from django.contrib.auth import get_user_model
from apps.people_master.models import AccountLink
from apps.tenancy.models import Membership, ScopeGrant
from apps.core.models import ReferenceAuditEvent
from django.db.migrations.executor import MigrationExecutor

User=get_user_model()
report={'auth_user_model':settings.AUTH_USER_MODEL,'counts':{'users':User.objects.count(),'usernames_over_100':User.objects.annotate(n=Length('username')).filter(n__gt=100).count(),'negative_user_ids':User.objects.filter(pk__lt=0).count(),'people_account_links':AccountLink.objects.count(),'memberships':Membership.objects.count(),'scope_grants':ScopeGrant.objects.count(),'reference_audit':ReferenceAuditEvent.objects.count()},'source_schema_conflicts':['Existing user_account uses signed BIGINT user_id, password VARCHAR(128), username VARCHAR(150), and Django framework compatibility columns.','SQL SELF role permission key is user_id but SELF override effective key is 0.','Existing AccountLink is consumed by business modules; replacing links requires an explicit compatibility plan.','Existing business authorization uses Django permissions plus Membership/ScopeGrant and explicit superuser branches.']}
with connection.cursor() as cursor:
    tables=set(connection.introspection.table_names(cursor))
    wanted=['student_user_account','employee_user_account','access_module','access_resource','access_action','permission','role','role_permission','user_role_assignment','user_permission_override','role_delegation','password_history','login_audit','activity_audit']
    report['iam_tables_present']=[t for t in wanted if t in tables]
    cursor.execute("SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='user_account' ORDER BY ORDINAL_POSITION")
    report['user_columns']=[list(row) for row in cursor.fetchall()]
    cursor.execute("SELECT TABLE_NAME,COLUMN_NAME,CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='user_account' ORDER BY TABLE_NAME,COLUMN_NAME")
    report['user_foreign_keys']=[list(row) for row in cursor.fetchall()]
    cursor.execute("SELECT COUNT(*) FROM file_object f LEFT JOIN user_account u ON u.user_id=f.uploaded_by_user_id WHERE f.uploaded_by_user_id IS NOT NULL AND u.user_id IS NULL")
    report['orphan_file_uploader_count']=cursor.fetchone()[0]
executor=MigrationExecutor(connection)
report['pending_migrations']=[m.app_label+'.'+m.name for m,backwards in executor.migration_plan(executor.loader.graph.leaf_nodes())]
report['module_flags']={name:bool(getattr(settings,name,False)) for name in ['STUDENT_SUPPORT_ENABLED','DOCUMENTS_EXIT_ENABLED','COMMUNICATION_ENABLED']}
Path('Manuals/M15_PREFLIGHT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'counts':report['counts'],'iam_tables_present':report['iam_tables_present'],'user_foreign_key_count':len(report['user_foreign_keys']),'orphan_file_uploader_count':report['orphan_file_uploader_count'],'pending_migrations':report['pending_migrations'],'module_flags':report['module_flags']},indent=2))
