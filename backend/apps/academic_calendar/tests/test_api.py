from datetime import date, time
from django.test import TestCase, RequestFactory, override_settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient
from apps.academic_calendar.models import AcademicYear, AcademicTerm, Semester, TimeSlot, CalendarAudit
from apps.academic_calendar.services import save_record, transition
from apps.academic_calendar import public
from apps.academic_calendar.policies import scoped
from .test_services import fixture


class CalendarAPITests(TestCase):
    def setUp(self):
        fixture(self)
        self.client=APIClient()
        self.client.force_authenticate(self.root)
        self.base='/api/v1/calendar/'

    def test_crud_filters_schema_and_lifecycle_routes(self):
        payload={'academic_year_id':self.year.pk,'term_code':'ODD','term_name':'First term','term_type':'ODD','start_date':'2026-06-01','end_date':'2026-12-31'}
        response=self.client.post(self.base+'academic-terms/',payload,format='json')
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['academic_term_id']
        path=f'{self.base}academic-terms/{pk}/'
        self.assertEqual(self.client.patch(path,{'status':'ACTIVE'},format='json').status_code,400)
        self.assertEqual(self.client.delete(path).status_code,405)
        self.assertEqual(self.client.get(self.base+'academic-terms/?academic_year_id=1.5').status_code,400)
        self.assertEqual(self.client.get(self.base+'academic-terms/?ordering=actor').status_code,400)
        self.assertEqual(self.client.get(self.base+'academic-terms/?search=First').data['count'],1)
        self.assertEqual(self.client.get(path).data['parent_label'],self.year.year_code)
        self.assertEqual(self.client.post(self.base+f'academic-years/{self.year.pk}/activate/',{},format='json').status_code,200)
        self.assertEqual(self.client.post(path+'open-registration/',{},format='json').status_code,200)
        self.assertEqual(self.client.post(path+'close/',{},format='json').status_code,400)
        self.assertEqual(self.client.post(path+'close/',{'reason':'Completed'},format='json').status_code,200)
        self.assertEqual(self.client.post(path+'reopen/',{'reason':'Correction'},format='json').status_code,200)
        semester=self.client.post(self.base+'semesters/',{'semester_number':1,'semester_name':'First'},format='json')
        self.assertEqual(semester.status_code,201,semester.data)
        self.assertEqual(self.client.post(self.base+f"semesters/{semester.data['semester_id']}/activate/",{},format='json').status_code,404)

    def test_slot_campus_scope_and_workflow_permission(self):
        self.client.force_authenticate(self.user)
        response=self.client.post(self.base+'time-slots/',{'campus_id':self.campus.pk,'slot_code':'ONE','start_time':'09:00','end_time':'10:00'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['time_slot_id']
        foreign=save_record(TimeSlot,{'campus_id':self.other_campus.pk,'slot_code':'SECRET','start_time':time(9),'end_time':time(10)},actor=self.root)
        self.assertEqual(self.client.get(self.base+'time-slots/').data['count'],1)
        self.assertEqual(self.client.get(self.base+f'time-slots/{foreign.pk}/').status_code,404)
        self.assertEqual(self.client.get(self.base+'campus-choices/').data['count'],1)
        self.assertEqual(self.client.post(self.base+'academic-years/',{},format='json').status_code,400)
        self.user.user_permissions.remove(Permission.objects.get(content_type__app_label='academic_calendar',codename='deactivate_timeslot'))
        response=self.client.post(self.base+f'time-slots/{pk}/deactivate/',{},format='json')
        self.assertEqual(response.status_code,404,response.data)
        self.assertTrue(TimeSlot.objects.get(pk=pk).is_active)
        self.assertEqual(CalendarAudit.objects.filter(resource='time-slots',record_id=pk).get().institution_id,self.institution.pk)

    def test_list_query_count_bounded_and_cache_disabled(self):
        for number in range(1,7):
            save_record(Semester,{'semester_number':number,'semester_name':f'Semester {number}'},actor=self.root)
        with CaptureQueriesContext(connection) as small:
            self.client.get(self.base+'semesters/?page_size=1')
        with CaptureQueriesContext(connection) as large:
            result=self.client.get(self.base+'semesters/?page_size=6')
        self.assertLessEqual(len(large),len(small)+1)
        self.assertEqual(result['Cache-Control'],'no-store')
        for path in ('metadata/','campus-choices/'):
            self.assertEqual(self.client.get(self.base+path)['Cache-Control'],'no-store')

    def test_selector_context_public_dtos_and_registration_boundaries(self):
        transition(AcademicYear,self.year.pk,'activate',actor=self.root)
        term=save_record(AcademicTerm,{'academic_year_id':self.year.pk,'term_code':'A','term_name':'A','term_type':'ODD','start_date':date(2026,6,1),'end_date':date(2026,12,1),'registration_start_date':date(2026,6,2)},actor=self.root)
        transition(AcademicTerm,term.pk,'open_registration',actor=self.root)
        kwargs={'actor':self.user,'institution_id':self.institution.pk}
        self.assertEqual(public.current_year(**kwargs).code,'2026-27')
        self.assertEqual(len(public.registration_terms(**kwargs,on_date=date(2026,6,1))),0)
        self.assertEqual(len(public.registration_terms(**kwargs,on_date=date(2026,6,2))),1)
        self.assertEqual(public.term_by_code(**kwargs,year_code='2026-27',term_code='A').id,term.pk)
        from rest_framework.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            public.current_year(actor=self.user,institution_id=self.other_campus.institution_id)

    def test_admin_scope_readonly_fields_and_audit_protection(self):
        request=RequestFactory().get('/admin/')
        request.user=self.user
        slot_admin=admin.site._registry[TimeSlot]
        year_admin=admin.site._registry[AcademicYear]
        self.assertTrue(slot_admin.has_add_permission(request))
        self.assertFalse(year_admin.has_add_permission(request))
        self.assertFalse(slot_admin.has_delete_permission(request))
        self.assertIn('is_active',slot_admin.get_readonly_fields(request))
        self.assertNotIn('delete_selected',slot_admin.get_actions(request))
        self.assertFalse(admin.site._registry[CalendarAudit].has_view_permission(request))
        request.user=self.root
        self.assertTrue(admin.site._registry[CalendarAudit].has_view_permission(request))
        transition(AcademicYear,self.year.pk,'close',actor=self.root,reason='Cancelled')
        self.year.refresh_from_db()
        self.assertIn('year_code',year_admin.get_readonly_fields(request,self.year))

    @override_settings(ACADEMIC_CALENDAR_ENABLED=False)
    def test_disabled_module_blocks_even_superuser_without_breaking_other_modules(self):
        self.assertEqual(self.client.get(self.base+'academic-years/').status_code,403)
        self.assertEqual(self.client.get('/api/v1/organization/universities/').status_code,200)
        self.assertFalse(scoped(AcademicYear,self.root).exists())

    def test_teacher_view_requires_permissions_and_cannot_write(self):
        self.grant.role='TEACHER';self.grant.save()
        self.client.force_authenticate(self.user)
        response=self.client.get(self.base+'metadata/')
        self.assertFalse(any(item['can_create'] for item in response.data['resources']))
        self.assertEqual(self.client.get(self.base+'academic-years/').data['count'],1)
        self.membership.is_active=False;self.membership.save()
        self.assertEqual(self.client.get(self.base+'academic-years/').data['count'],0)

    def test_admin_writes_audit_and_bulk_failure_rolls_back(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        request=RequestFactory().post('/admin/',{'reason':'Reviewed'})
        request.user=self.root
        request.session={}
        request._messages=FallbackStorage(request)
        model_admin=admin.site._registry[AcademicYear]
        second=AcademicYear(year_code='2027-28',start_date=date(2027,6,1),end_date=date(2028,5,31))
        model_admin.save_model(request,second,None,False)
        self.assertIsNotNone(second.pk)
        self.assertTrue(CalendarAudit.objects.filter(resource='academic-years',record_id=second.pk,action='create').exists())
        model_admin.activate(request,AcademicYear.objects.filter(pk__in=[self.year.pk,second.pk]))
        self.assertEqual(AcademicYear.objects.filter(status='ACTIVE').count(),0)
        self.assertEqual(CalendarAudit.objects.filter(action='activate').count(),0)

    def test_response_request_id_matches_audit_and_invalid_reason_is_400(self):
        path=self.base+f'academic-years/{self.year.pk}/'
        response=self.client.patch(path,{'year_code':'NEW'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response['X-Request-ID'],CalendarAudit.objects.first().correlation_id)
        self.assertEqual(self.client.post(path+'close/',{'reason':'Done','status':'CLOSED'},format='json').status_code,400)

    def test_slot_scope_rejects_wrong_campus_and_deactivated_parent_assignment(self):
        from apps.organization.models import Campus
        second=Campus.objects.create(institution=self.institution,campus_code='SECOND',campus_name='Second')
        self.grant.role='CAMPUS_ADMIN';self.grant.campus=self.campus;self.grant.full_clean();self.grant.save()
        self.client.force_authenticate(self.user)
        payload={'campus_id':second.pk,'slot_code':'X','start_time':'09:00','end_time':'10:00'}
        self.assertEqual(self.client.post(self.base+'time-slots/',payload,format='json').status_code,400)
        self.campus.is_active=False;self.campus.save()
        payload['campus_id']=self.campus.pk
        self.assertEqual(self.client.post(self.base+'time-slots/',payload,format='json').status_code,409)
