"""Produce query-plan evidence using temporary representative rows; roll back all data."""
import os
from datetime import date, timedelta, time
from uuid import uuid4
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
django.setup()
from django.db import transaction, connection
from django.contrib.auth import get_user_model
from apps.academic_calendar.models import AcademicYear, AcademicTerm, TimeSlot
from apps.academic_calendar import selectors
from apps.organization.models import University, Institution, Campus
from pathlib import Path

output=[]
with transaction.atomic():
    tag=uuid4().hex[:6].upper()
    actor=get_user_model().objects.create(username='plan-'+tag,is_superuser=True,is_active=True)
    uni=University.objects.create(university_code='PLAN'+tag,university_name='Temporary plan sample')
    institution=Institution.objects.create(university=uni,institution_code='PLAN'+tag,institution_name='Temporary plan sample')
    campus=Campus.objects.create(institution=institution,campus_code='PLAN',campus_name='Temporary plan sample')
    for index in range(80):
        start=date(2000+index,1,1)
        year=AcademicYear.objects.create(year_code=f'{tag}{index:02}',start_date=start,end_date=start+timedelta(days=364),status='ACTIVE' if index==26 else 'CLOSED')
        for number in range(3):
            AcademicTerm.objects.create(academic_year=year,term_code=f'T{number}',term_name=f'Term {number}',term_type='OTHER',start_date=start,end_date=start+timedelta(days=120),status='REGISTRATION_OPEN' if index==26 else 'CLOSED')
    for hour in range(24):
        TimeSlot.objects.create(campus=campus,slot_code=f'S{hour}',start_time=time(hour),end_time=time(hour,30))
    queries={
        'Current shared year': AcademicYear.objects.filter(status='ACTIVE').order_by('-start_date','pk'),
        'Open registration terms': selectors.registration_terms(actor=actor,institution_id=institution.pk,on_date=date(2026,1,10)),
        'Active terms': selectors.active_terms(actor=actor,institution_id=institution.pk),
        'Campus slots': selectors.campus_slots(actor=actor,institution_id=institution.pk,campus_id=campus.pk),
        'Term natural key': AcademicTerm.objects.filter(academic_year__year_code=f'{tag}26',term_code='T1'),
    }
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        output.append('MySQL version: '+cursor.fetchone()[0])
    for title,query in queries.items():
        output.extend(['\n## '+title,'```text',query.explain(),'```'])
    transaction.set_rollback(True)
Path('Manuals/M3_QUERY_PLANS.md').write_text('# Calendar MySQL query plans\n\nTemporary fixture: 80 years, 240 terms, 24 campus slots; all rows rolled back. Auto-increment gaps can remain. Plans are diagnostic samples, not production load benchmarks.\n\n'+'\n'.join(output),encoding='utf-8')
