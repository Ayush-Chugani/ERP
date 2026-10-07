from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('teaching_timetable', '0001_initial')]
    operations = [migrations.RunSQL(
        'ALTER TABLE timetable_session ADD CONSTRAINT fk_m8_session_faculty_owner '
        'FOREIGN KEY (faculty_assignment_id, course_offering_section_id) '
        'REFERENCES faculty_course_assignment (faculty_assignment_id, course_offering_section_id)',
        'ALTER TABLE timetable_session DROP FOREIGN KEY fk_m8_session_faculty_owner',
    )]
