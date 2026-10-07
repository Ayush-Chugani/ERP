from datetime import date
from decimal import Decimal
from django.db import connection,IntegrityError,transaction
from django.test import TestCase
from django.utils import timezone
from apps.people_master.tests.test_services import fixture
from apps.people_master.models import Employee
from apps.employee_hr import models as m

class HistoryContractTests(TestCase):
    def setUp(self):
        fixture(self)
        self.employee=Employee.objects.create(institution=self.institution,employment_source=self.source,employee_number='M16-SYNTHETIC',first_name='Synthetic',display_name='Synthetic Employee',joining_date=date(2020,1,1),employment_type='REGULAR')
        self.level=m.QualificationLevel.objects.create(level_code='SYNTHETIC',level_name='Synthetic Level')

    def qualification(self,**values):
        return m.EmployeeQualification.objects.create(employee=self.employee,qualification_level=self.level,degree_certificate_name='Synthetic degree',**values)

    def test_highest_unique_includes_pursuing_and_excludes_soft_deleted(self):
        first=self.qualification(is_highest_qualification=True,qualification_status='PURSUING')
        with self.assertRaises(IntegrityError),transaction.atomic():self.qualification(is_highest_qualification=True)
        first.deleted_at=timezone.now();first.save(update_fields=['deleted_at'])
        current=self.qualification(is_highest_qualification=True)
        current.refresh_from_db();self.assertEqual(current.active_highest_employee_id,self.employee.pk)

    def test_database_dates_scores_and_marks(self):
        cases=[dict(start_date=date(2021,1,1),completion_date=date(2020,1,1)),dict(percentage=Decimal('100.01')),dict(cgpa=Decimal('-1')),dict(cgpa_scale=0),dict(cgpa=5,cgpa_scale=4),dict(marks_obtained=11,maximum_marks=10)]
        for values in cases:
            with self.subTest(values=values),self.assertRaises(IntegrityError),transaction.atomic():self.qualification(**values)
        self.qualification(percentage=100,cgpa=4,cgpa_scale=4,marks_obtained=10,maximum_marks=10)

    def test_employment_override_and_negative_salary(self):
        organization=m.PreviousOrganization.objects.create(organization_name='Synthetic employer')
        values=dict(employee=self.employee,previous_organization=organization,designation='Synthetic role',employment_type='FULL_TIME',employment_start_date=date(2020,1,1))
        row=m.EmployeePreviousEmployment.objects.create(experience_days=17,**values)
        self.assertEqual(row.experience_days,17)
        for invalid in [dict(last_drawn_salary=-1),dict(employment_end_date=date(2019,1,1))]:
            with self.assertRaises(IntegrityError),transaction.atomic():m.EmployeePreviousEmployment.objects.create(**values,**invalid)

    def test_owner_constraints_and_server_update_timestamp(self):
        with connection.cursor() as c:
            for table,name in [('employee_qualification','uq_employee_qualification_owner'),('employee_previous_employment','uq_employee_previous_employment_owner')]:
                c.execute('SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s ORDER BY SEQ_IN_INDEX',[table,name])
                self.assertEqual([r[0] for r in c.fetchall()],[table+'_id','employee_id'])
                c.execute("SELECT EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='updated_at'",[table])
                self.assertIn('on update CURRENT_TIMESTAMP'.lower(),c.fetchone()[0].lower())

    def test_every_source_column_is_represented(self):
        import re
        from apps.employee_hr.migrations._history_ddl import DDL
        for model,ddl in zip((m.EmployeeQualification,m.EmployeePreviousEmployment),DDL):
            expected=set(re.findall(r'^\s*(\w+) (?:BIGINT|SMALLINT|TINYINT|INT|VARCHAR|CHAR|BOOLEAN|TIMESTAMP|ENUM|DATE|YEAR|DECIMAL)\b',ddl,re.M))
            self.assertEqual({f.column for f in model._meta.local_fields},expected)

    def test_source_foreign_key_names_and_signed_actor_compatibility(self):
        import re
        from apps.employee_hr.migrations._history_ddl import DDL
        with connection.cursor() as cursor:
            for ddl in DDL:
                table=re.search(r'CREATE TABLE (\w+)',ddl)[1]
                expected=set(re.findall(r'CONSTRAINT (\w+) FOREIGN KEY',ddl))
                cursor.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s AND CONSTRAINT_TYPE='FOREIGN KEY'",[table])
                self.assertEqual({r[0] for r in cursor.fetchall()},expected)
                cursor.execute("SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='created_by_user_id'",[table])
                self.assertEqual(cursor.fetchone()[0],'bigint')
