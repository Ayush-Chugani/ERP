from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date, time
from django.test import TransactionTestCase
from django.db import connections
from django.contrib.auth import get_user_model
from apps.academic_calendar.models import AcademicYear, TimeSlot, CalendarAudit
from apps.academic_calendar.services import save_record, transition, CalendarConflict
from .test_services import fixture


class CalendarConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixture(self)

    def race(self, work):
        barrier=Barrier(2)
        def run(index):
            try:
                actor=get_user_model().objects.get(pk=self.root.pk)
                barrier.wait(timeout=10)
                work(index,actor)
                return 'committed'
            except CalendarConflict:
                return 'conflict'
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(run,range(2)))
        self.assertCountEqual(result,['committed','conflict'])

    def test_concurrent_year_activation(self):
        second=save_record(AcademicYear,{'year_code':'2027-28','start_date':date(2027,6,1),'end_date':date(2028,5,31)},actor=self.root)
        ids=[self.year.pk,second.pk]
        self.race(lambda index,actor:transition(AcademicYear,ids[index],'activate',actor=actor))
        self.assertEqual(AcademicYear.objects.filter(status='ACTIVE').count(),1)
        self.assertEqual(CalendarAudit.objects.filter(action='activate').count(),1)

    def test_concurrent_overlapping_slots(self):
        self.race(lambda index,actor:save_record(TimeSlot,{'campus_id':self.campus.pk,'slot_code':f'S{index}','start_time':time(9),'end_time':time(10)},actor=actor))
        self.assertEqual(TimeSlot.objects.count(),1)
        self.assertEqual(CalendarAudit.objects.filter(resource='time-slots').count(),1)
