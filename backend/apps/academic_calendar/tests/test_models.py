from datetime import date, time
from django.test import TestCase
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from apps.academic_calendar.models import AcademicYear, AcademicTerm, Semester, TimeSlot
from .test_services import fixture


class CalendarSchemaTests(TestCase):
    def setUp(self):
        fixture(self)

    def test_each_baseline_unique_and_foreign_key(self):
        term_values=dict(academic_year=self.year,term_code='TERM',term_name='Term',term_type='ODD',start_date=date(2026,6,1),end_date=date(2026,6,1))
        AcademicTerm.objects.create(**term_values)
        slot_values=dict(campus=self.campus,slot_code='SLOT',start_time=time(9),end_time=time(10))
        TimeSlot.objects.create(**slot_values)
        Semester.objects.create(semester_number=1,semester_name='One')
        cases=[
            (AcademicYear,dict(year_code=self.year.year_code,start_date=date(2027,1,1),end_date=date(2028,1,1))),
            (AcademicTerm,term_values),
            (Semester,dict(semester_number=1,semester_name='Different')),
            (Semester,dict(semester_number=2,semester_name='ONE')),
            (TimeSlot,slot_values),
            (AcademicTerm,{**{k:v for k,v in term_values.items() if k!='academic_year'},'academic_year_id':65535,'term_code':'MISSING'}),
            (TimeSlot,{**{k:v for k,v in slot_values.items() if k!='campus'},'campus_id':65535,'slot_code':'MISSING'}),
        ]
        for model,values in cases:
            with self.subTest(table=model._meta.db_table),self.assertRaises(IntegrityError),transaction.atomic():
                model.objects.create(**values)
        with self.assertRaises(ProtectedError):
            self.campus.delete()

    def test_mysql_named_checks_collations_and_unsigned_widths(self):
        expected={
            'academic_year':('smallint unsigned',['chk_academic_year_dates','chk_academic_year_status']),
            'academic_term':('int unsigned',['uq_term_code','chk_term_dates','chk_term_registration_dates','chk_academic_term_type','chk_academic_term_status']),
            'semester':('tinyint unsigned',['chk_semester_number']),
            'time_slot':('smallint unsigned',['uq_time_slot','chk_time_slot']),
        }
        with connection.cursor() as cursor:
            for table,(width,names) in expected.items():
                cursor.execute(f'SHOW CREATE TABLE `{table}`')
                sql=cursor.fetchone()[1]
                self.assertIn(width,sql)
                self.assertIn('utf8mb4_unicode_ci',sql)
                for name in names:
                    self.assertIn(name,sql)
