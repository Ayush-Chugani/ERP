from datetime import date, time
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction, connection
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from apps.organization.models import University, Institution, Campus
from apps.tenancy.models import Membership, ScopeGrant, InstitutionModule
from apps.academic_calendar.models import AcademicYear, AcademicTerm, Semester, TimeSlot, CalendarAudit
from apps.academic_calendar.services import save_record, transition, CalendarConflict
from apps.academic_calendar.policies import scoped
from apps.academic_calendar.scheduling import slot_datetimes


def fixture(owner):
    owner.root = get_user_model().objects.create_superuser(username='root', password='test')
    owner.user = get_user_model().objects.create_user(username='manager', password='test')
    university = University.objects.create(university_code='UNI', university_name='University')
    owner.institution = Institution.objects.create(university=university, institution_code='A', institution_name='A')
    other = Institution.objects.create(university=university, institution_code='B', institution_name='B')
    owner.campus = Campus.objects.create(institution=owner.institution, campus_code='A', campus_name='A')
    owner.other_campus = Campus.objects.create(institution=other, campus_code='B', campus_name='B')
    owner.activation = InstitutionModule.objects.create(institution=owner.institution, academic_calendar=True)
    owner.membership = Membership.objects.create(user=owner.user, institution=owner.institution)
    owner.grant = ScopeGrant.objects.create(membership=owner.membership, role='INSTITUTION_ADMIN')
    owner.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='academic_calendar'))
    owner.year = save_record(AcademicYear, {'year_code':'2026-27', 'start_date':date(2026,6,1), 'end_date':date(2027,5,31)}, actor=owner.root)


class CalendarServiceTests(TestCase):
    def setUp(self):
        fixture(self)

    def term(self, **overrides):
        return save_record(AcademicTerm, dict(academic_year_id=self.year.pk, term_code='ODD', term_name='Odd term', term_type='ODD', start_date=date(2026,6,1), end_date=date(2026,12,31), **overrides), actor=self.root)

    def slot(self, code='S1', start=time(9), end=time(10), **overrides):
        values = dict(campus_id=self.campus.pk, slot_code=code, start_time=start, end_time=end)
        values.update(overrides)
        return save_record(TimeSlot, values, actor=self.user)

    def test_lifecycle_containment_cardinality_and_retry(self):
        term = self.term()
        with self.assertRaises(CalendarConflict):
            transition(AcademicTerm, term.pk, 'activate', actor=self.root)
        transition(AcademicYear, self.year.pk, 'activate', actor=self.root)
        before = CalendarAudit.objects.count()
        transition(AcademicYear, self.year.pk, 'activate', actor=self.root)
        self.assertEqual(CalendarAudit.objects.count(), before)
        transition(AcademicTerm, term.pk, 'open_registration', actor=self.root)
        transition(AcademicTerm, term.pk, 'activate', actor=self.root)
        with self.assertRaises(CalendarConflict):
            transition(AcademicYear, self.year.pk, 'close', actor=self.root, reason='End')
        transition(AcademicTerm, term.pk, 'close', actor=self.root, reason='Complete')
        with self.assertRaises(CalendarConflict):
            save_record(AcademicTerm, {'term_name':'Changed'}, actor=self.root, pk=term.pk)
        with self.assertRaises(ValidationError):
            transition(AcademicTerm, term.pk, 'reopen', actor=self.root)
        transition(AcademicTerm, term.pk, 'reopen', actor=self.root, reason='Correction')
        with self.assertRaises(CalendarConflict):
            save_record(AcademicYear, {'end_date':date(2026,8,1)}, actor=self.root, pk=self.year.pk)
        other = save_record(AcademicYear, {'year_code':'2027-28','start_date':date(2027,6,1),'end_date':date(2028,5,31)}, actor=self.root)
        with self.assertRaises(CalendarConflict):
            transition(AcademicYear, other.pk, 'activate', actor=self.root)

    def test_nullable_registration_and_outside_year(self):
        term = self.term(registration_start_date=date(2026,6,1))
        self.assertIsNone(term.registration_end_date)
        with self.assertRaises(ValidationError):
            save_record(AcademicTerm, {'registration_end_date':date(2028,1,1)}, actor=self.root, pk=term.pk)
        with self.assertRaises(ValidationError):
            save_record(AcademicTerm, {'registration_end_date':date(2026,5,1)}, actor=self.root, pk=term.pk)

    def test_slot_adjacency_break_overlap_activation_and_isolation(self):
        first = self.slot()
        self.slot('S2', time(10), time(11))
        with self.assertRaises(CalendarConflict) as error:
            self.slot('S3', time(9,30), time(10,30))
        self.assertEqual(int(error.exception.detail['conflicting_slot_id']), first.pk)
        self.slot('BREAK', time(9,15), time(9,45), is_break=True)
        transition(TimeSlot, first.pk, 'deactivate', actor=self.user)
        self.slot('REPLACEMENT')
        with self.assertRaises(CalendarConflict):
            transition(TimeSlot, first.pk, 'activate', actor=self.user)
        with self.assertRaises(ValidationError):
            self.slot('CROSS', campus_id=self.other_campus.pk)
        with self.assertRaises(ValidationError):
            self.slot('NIGHT', time(23), time(1))

    def test_permissions_activation_and_limits(self):
        with self.assertRaises(PermissionDenied):
            save_record(Semester, {'semester_number':1,'semester_name':'One'}, actor=self.user)
        self.assertEqual(scoped(AcademicYear, self.user).count(), 1)
        self.activation.academic_calendar=False
        self.activation.save()
        self.assertFalse(scoped(AcademicYear, self.user).exists())
        with self.assertRaises(PermissionDenied):
            self.slot()
        self.activation.academic_calendar=True
        self.activation.save()
        self.grant.record_limits={'time-slots':[]}
        self.grant.save()
        with self.assertRaises(PermissionDenied):
            self.slot()
        self.assertFalse(TimeSlot.objects.exists())

    def test_audit_rollback_and_collation(self):
        with patch('apps.academic_calendar.services.CalendarAudit.objects.create', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.slot()
        self.assertFalse(TimeSlot.objects.exists())
        save_record(Semester, {'semester_number':1,'semester_name':'Café'}, actor=self.root)
        with self.assertRaises(CalendarConflict):
            save_record(Semester, {'semester_number':2,'semester_name':'CAFE'}, actor=self.root)
        self.assertEqual(Semester.objects.count(), 1)
        event=CalendarAudit.objects.first()
        with self.assertRaises(Exception):
            event.delete()

    def test_database_constraints_unsigned_and_timezone(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicYear.objects.filter(pk=self.year.pk).update(end_date=date(2020,1,1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Semester.objects.create(semester_number=0,semester_name='Zero')
        with connection.cursor() as cursor:
            cursor.execute('SHOW CREATE TABLE academic_term')
            sql=cursor.fetchone()[1]
            self.assertIn('int unsigned', sql)
            self.assertIn('chk_term_registration_dates', sql)
        slot=self.slot()
        with self.assertRaises(ValidationError):
            slot_datetimes(slot,date(2026,1,1))
        with override_settings(CALENDAR_CAMPUS_TIMEZONES={str(self.campus.pk):'Asia/Kolkata'}):
            start,end=slot_datetimes(slot,date(2026,1,1))
            self.assertEqual((end-start).total_seconds(),3600)
        slot.start_time=time(2,15);slot.end_time=time(3,15)
        with override_settings(CALENDAR_CAMPUS_TIMEZONES={str(self.campus.pk):'America/New_York'}):
            with self.assertRaises(ValidationError):
                slot_datetimes(slot,date(2026,3,8))

    def test_record_limited_overlap_does_not_disclose_hidden_slot(self):
        hidden=save_record(TimeSlot,{'campus_id':self.campus.pk,'slot_code':'CONFIDENTIAL','start_time':time(9),'end_time':time(10)},actor=self.root)
        visible=save_record(TimeSlot,{'campus_id':self.campus.pk,'slot_code':'VISIBLE','start_time':time(11),'end_time':time(12)},actor=self.root)
        self.grant.record_limits={'time-slots':[visible.pk]};self.grant.save()
        with self.assertRaises(CalendarConflict) as error:
            save_record(TimeSlot,{'start_time':time(9),'end_time':time(10)},actor=self.user,pk=visible.pk)
        self.assertNotIn('CONFIDENTIAL',str(error.exception.detail))
        self.assertNotIn('conflicting_slot_id',str(error.exception.detail))
        self.assertEqual(TimeSlot.objects.get(pk=hidden.pk).slot_code,'CONFIDENTIAL')

    def test_database_bypasses_still_reject_local_invalid_values(self):
        term=self.term()
        for values in ({'term_type':'BAD'}, {'status':'INVALID'}, {'end_date':date(2025,1,1)}, {'registration_start_date':date(2026,8,1),'registration_end_date':date(2026,7,1)}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                AcademicTerm.objects.filter(pk=term.pk).update(**values)
        slot=self.slot()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeSlot.objects.filter(pk=slot.pk).update(end_time=time(8))
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.year.delete()

    def test_closed_year_blocks_child_changes_and_dst_ambiguity(self):
        term=self.term()
        transition(AcademicTerm,term.pk,'close',actor=self.root,reason='Cancelled')
        transition(AcademicYear,self.year.pk,'close',actor=self.root,reason='Cancelled')
        with self.assertRaises(CalendarConflict):
            transition(AcademicTerm,term.pk,'reopen',actor=self.root,reason='Retry')
        slot=self.slot(start=time(1,15),end=time(2,15))
        with override_settings(CALENDAR_CAMPUS_TIMEZONES={str(self.campus.pk):'America/New_York'}):
            with self.assertRaises(ValidationError):
                slot_datetimes(slot,date(2026,11,1))


    def test_all_public_selectors_return_scoped_read_contracts(self):
        from apps.academic_calendar import public
        transition(AcademicYear,self.year.pk,'activate',actor=self.root)
        term=self.term()
        transition(AcademicTerm,term.pk,'activate',actor=self.root)
        slot=self.slot()
        semester=save_record(Semester,{'semester_number':1,'semester_name':'One'},actor=self.root)
        context={'actor':self.user,'institution_id':self.institution.pk}
        self.assertEqual(public.active_terms(**context)[0].id,term.pk)
        self.assertEqual(public.semesters(**context),((semester.pk,1,'One'),))
        self.assertEqual(public.campus_slots(**context,campus_id=self.campus.pk)[0].id,slot.pk)
        self.assertEqual(public.campus_slots(**context,campus_id=self.other_campus.pk),())
        self.user.user_permissions.clear()
        self.user=type(self.user).objects.get(pk=self.user.pk)
        self.assertIsNone(public.current_year(actor=self.user,institution_id=self.institution.pk))
