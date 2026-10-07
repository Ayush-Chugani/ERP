"""Temporary synthetic dataset; every data write rolls back."""
import os
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.db import transaction,connection
from apps.people_master.models import Student
from apps.organization.models import University,Institution
from uuid import uuid4
lines=['# M5 MySQL query plans','','Synthetic 1,000-student fixture, rolled back. No personal data or production load claim.','']
with transaction.atomic():
    code=uuid4().hex[:12].upper()
    university=University.objects.create(university_code=code,university_name='Synthetic preflight')
    institution=Institution.objects.create(university=university,institution_code=code,institution_name='Synthetic preflight')
    Student.objects.bulk_create([Student(institution=institution,student_number=code+str(i),first_name='Synthetic',display_name='Synthetic '+str(i)) for i in range(1000)])
    for title,query in [('Institution/status directory',Student.objects.filter(institution=institution,student_status='APPLICANT').order_by('student_number')[:25]),('Institution identifier lookup',Student.objects.filter(institution=institution,student_number=code+'10')),('Scoped name search',Student.objects.filter(institution=institution,display_name__icontains='100')[:25])]:
        sql,args=query.query.sql_with_params()
        with connection.cursor() as cursor:
            cursor.execute('EXPLAIN FORMAT=TREE '+sql,args)
            lines += ['## '+title,'```text','\n'.join(str(row[0]) for row in cursor.fetchall()),'```','']
    transaction.set_rollback(True)
Path('Manuals/M5_QUERY_PLANS.md').write_text('\n'.join(lines),encoding='utf-8')
print('M5 query plans saved; synthetic data rolled back.')
