from django.db import migrations


KEYS = [
    ('admission_application', 'fk_m6_application_specialization', '(specialization_id, programme_id)', 'programme_specialization(specialization_id, programme_id)'),
    ('student_programme_enrolment', 'fk_m6_enrolment_specialization', '(specialization_id, programme_id)', 'programme_specialization(specialization_id, programme_id)'),
    ('student_programme_enrolment', 'fk_m6_conversion_student', '(application_id, student_id)', 'admission_application(application_id, admitted_student_id)'),
    ('student_programme_enrolment', 'fk_m6_enrolment_scheme_programme', '(curriculum_scheme_id, programme_id)', 'curriculum_scheme(curriculum_scheme_id, programme_id)'),
]


class Migration(migrations.Migration):
    dependencies = [('admission_enrolment', '0001_initial'), ('curriculum_catalog', '0003_curriculumscheme_uq_m6_scheme_programme')]
    operations = [migrations.RunSQL(
        f'ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY {cols} REFERENCES {target}',
        f'ALTER TABLE {table} DROP FOREIGN KEY {name}',
    ) for table, name, cols, target in KEYS]
