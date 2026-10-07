from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("people_master", "0002_peopleaudit_peopleevent_peoplerevision_and_more")
    ]
    operations = [
        migrations.RunSQL(
            "ALTER TABLE employee_assignment ADD CONSTRAINT fk_employee_assignment_department_campus FOREIGN KEY (department_id, campus_id) REFERENCES department(department_id, campus_id)",
            "ALTER TABLE employee_assignment DROP FOREIGN KEY fk_employee_assignment_department_campus",
        )
    ]
