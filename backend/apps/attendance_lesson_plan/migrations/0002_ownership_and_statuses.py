from django.db import migrations

def seed(apps,schema_editor):
    Status=apps.get_model('attendance_lesson_plan','AttendanceStatus')
    for code,name,present in [('PRESENT','Present',True),('ABSENT','Absent',False),('LATE','Late',False),('EXCUSED','Excused',False),('ON_DUTY','On duty',False)]:
        Status.objects.get_or_create(status_code=code,defaults={'status_name':name,'counts_as_present':present,'is_active':True})

def fk(table,name,columns,target,target_columns):
    return migrations.RunSQL(f'ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({columns}) REFERENCES {target} ({target_columns})',f'ALTER TABLE {table} DROP FOREIGN KEY {name}')

class Migration(migrations.Migration):
    dependencies=[
        ('attendance_lesson_plan','0001_initial'),
        ('teaching_timetable','0006_publishedoccurrence_uq_m9_occurrence_section_and_more'),
    ]
    operations=[
        fk('class_session','fk_m9_faculty_section','faculty_assignment_id, course_offering_section_id','faculty_course_assignment','faculty_assignment_id, course_offering_section_id'),
        fk('class_session','fk_m9_timetable_section','timetable_session_id, course_offering_section_id','timetable_session','timetable_session_id, course_offering_section_id'),
        fk('class_session','fk_m9_occurrence_section','occurrence_id, course_offering_section_id','platform_m8_occurrence','id, course_offering_section_id'),
        fk('class_session','fk_m9_session_type','course_offering_section_id, session_type','course_offering_section','course_offering_section_id, session_type'),
        fk('student_attendance','fk_m9_attendance_session','class_session_id, course_offering_section_id','class_session','class_session_id, course_offering_section_id'),
        fk('student_attendance','fk_m9_attendance_roster','course_offering_section_student_id, course_offering_section_id','course_offering_section_student','course_offering_section_student_id, course_offering_section_id'),
        migrations.RunPython(seed,migrations.RunPython.noop),
    ]
