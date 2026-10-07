from django.db import migrations
PAIRS=[('assessment_event','fk_m10_event_component','assessment_component_id,course_offering_id','assessment_component','assessment_component_id,course_offering_id'),('student_assessment_mark','fk_m10_mark_event','assessment_event_id,course_offering_id','assessment_event','assessment_event_id,course_offering_id'),('student_assessment_mark','fk_m10_mark_registration','course_registration_id,course_offering_id','student_course_registration','course_registration_id,course_offering_id')]
class Migration(migrations.Migration):
    dependencies=[('assessments_results','0001_initial')]
    operations=[migrations.RunSQL(f'ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({cols}) REFERENCES {parent} ({keys})',f'ALTER TABLE {table} DROP FOREIGN KEY {name}') for table,name,cols,parent,keys in PAIRS]
