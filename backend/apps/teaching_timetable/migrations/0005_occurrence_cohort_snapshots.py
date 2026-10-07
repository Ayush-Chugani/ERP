import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('teaching_timetable', '0004_alter_facultyassignment_options_and_more')]
    operations = [
        migrations.AddField('publishedoccurrence', 'class_section', models.ForeignKey(
            to='term_registration.classsection', on_delete=django.db.models.deletion.PROTECT,
            related_name='+', null=True)),
        migrations.AddField('publishedoccurrence', 'class_batch', models.ForeignKey(
            to='term_registration.classbatch', on_delete=django.db.models.deletion.PROTECT,
            related_name='+', null=True, blank=True)),
        migrations.RunSQL(
            'UPDATE platform_m8_occurrence o JOIN course_offering_section s '
            'ON o.course_offering_section_id = s.course_offering_section_id '
            'SET o.class_section_id = s.class_section_id, o.class_batch_id = s.class_batch_id',
            migrations.RunSQL.noop),
        migrations.AlterField('publishedoccurrence', 'class_section', models.ForeignKey(
            to='term_registration.classsection', on_delete=django.db.models.deletion.PROTECT,
            related_name='+')),
    ]
