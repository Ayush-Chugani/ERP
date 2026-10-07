from django.db import migrations,models
import django.db.models.deletion


def attach(apps,schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM file_object f LEFT JOIN user_account u ON u.user_id=f.uploaded_by_user_id WHERE f.uploaded_by_user_id IS NOT NULL AND u.user_id IS NULL')
        if cursor.fetchone()[0]: raise RuntimeError('Reconcile orphan file uploaders before M15 integration.')
        cursor.execute('ALTER TABLE file_object MODIFY uploaded_by_user_id BIGINT NULL, ADD CONSTRAINT fk_file_object_uploaded_by FOREIGN KEY (uploaded_by_user_id) REFERENCES user_account(user_id)')

class Migration(migrations.Migration):
    atomic=False
    dependencies=[('documents_exit','0002_shared_file_permissions'),('accounts','0003_m15_session_version'),('identity_access','0004_support_sessions')]
    operations=[migrations.SeparateDatabaseAndState(database_operations=[migrations.RunPython(attach)],state_operations=[migrations.RenameField(model_name='fileobject',old_name='uploaded_by_user_id',new_name='uploaded_by_user'),migrations.AlterField(model_name='fileobject',name='uploaded_by_user',field=models.ForeignKey('accounts.User',on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name='+',db_column='uploaded_by_user_id'))])]
