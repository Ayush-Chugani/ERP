from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("curriculum_catalog", "0001_initial")]
    operations = [
        migrations.RunSQL(
            "ALTER TABLE curriculum_scheme ADD CONSTRAINT fk_scheme_specialization_programme FOREIGN KEY (specialization_id, programme_id) REFERENCES programme_specialization (specialization_id, programme_id)",
            "ALTER TABLE curriculum_scheme DROP FOREIGN KEY fk_scheme_specialization_programme",
        )
    ]
