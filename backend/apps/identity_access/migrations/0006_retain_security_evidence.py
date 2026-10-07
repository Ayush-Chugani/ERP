from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('identity_access','0005_override_revocation'),('documents_exit','0003_m15_uploader_identity'),('accounts','0003_m15_session_version')]
    operations=[migrations.RunPython(migrations.RunPython.noop)]
