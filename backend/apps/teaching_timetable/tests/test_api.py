from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from . import test_services as fixtures
from apps.teaching_timetable import models as m


@override_settings(ADMISSION_ENROLMENT_ENABLED=True, PEOPLE_MASTER_ENABLED=True,
                   TERM_REGISTRATION_ENABLED=True, TEACHING_TIMETABLE_ENABLED=True)
class ApiTests(TestCase):
    setUp = fixtures.TimetableTests.setUp
    session = fixtures.TimetableTests.session
    transition = fixtures.TimetableTests.transition
    publish = fixtures.TimetableTests.publish
    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_command_idempotency_and_payload_collision(self):
        client = self.client_for(self.root)
        data = {'offering_id': self.offering.pk, 'name': 'Revision', 'reason': 'Plan'}
        url = '/api/v1/timetable/commands/create-revision/'
        first = client.post(url, data, format='json', HTTP_IDEMPOTENCY_KEY='same-request')
        self.assertEqual(first.status_code, 200, first.data)
        second = client.post(url, data, format='json', HTTP_IDEMPOTENCY_KEY='same-request')
        self.assertEqual(first.data, second.data)
        data['name'] = 'Changed'
        self.assertEqual(client.post(url, data, format='json', HTTP_IDEMPOTENCY_KEY='same-request').status_code, 409)

    def test_unauthorized_lists_and_commands(self):
        user = get_user_model().objects.create_user(username='outsider')
        client = self.client_for(user)
        self.assertEqual(client.get('/api/v1/timetable/revisions/').status_code, 403)
        self.assertEqual(client.post('/api/v1/timetable/commands/create-revision/',
            {'offering_id': self.offering.pk, 'name': 'No', 'reason': 'No'},
            format='json', HTTP_IDEMPOTENCY_KEY='no').status_code, 403)

    def test_mass_assignment_rejected(self):
        response = self.client_for(self.root).post('/api/v1/timetable/commands/create-revision/',
            {'offering_id': self.offering.pk, 'name': 'No', 'reason': 'No', 'status': 'PUBLISHED'},
            format='json', HTTP_IDEMPOTENCY_KEY='mass')
        self.assertEqual(response.status_code, 400)

    def test_occurrence_endpoint_never_returns_drafts(self):
        self.session()
        client = self.client_for(self.root)
        url = '/api/v1/timetable/occurrences/?date_from=2026-09-01&date_to=2026-09-30'
        self.assertEqual(client.get(url).data['results'], [])
        self.publish()
        response = client.get(url)
        self.assertEqual(len(response.data['results']), 4)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn('student_ids', response.data['results'][0])

    def test_unbounded_occurrence_query_rejected(self):
        response = self.client_for(self.root).get('/api/v1/timetable/occurrences/?date_from=2020-01-01&date_to=2030-01-01')
        self.assertEqual(response.status_code, 400)

    def test_record_limits_filter_reads_and_reject_writes(self):
        from django.contrib.auth.models import Permission
        from apps.tenancy.models import InstitutionModule, Membership, ScopeGrant
        user = get_user_model().objects.create_user(username='limited-planner')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='teaching_timetable', codename='manage_timetable'))
        InstitutionModule.objects.filter(institution=self.institution).update(teaching_timetable=True)
        membership = Membership.objects.create(user=user, institution=self.institution)
        ScopeGrant.objects.create(membership=membership, role='INSTITUTION_ADMIN', record_limits={'employees': []})
        client = self.client_for(user)
        response = client.get('/api/v1/timetable/assignments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response.data['count'], 0)
        response = client.get(f'/api/v1/timetable/availability/?kind=faculty&resource_id={self.employee.pk}&date_from=2026-09-01&date_to=2026-09-30')
        self.assertEqual(response.status_code, 404)
        response = client.post('/api/v1/timetable/commands/create-assignment/', {
            'course_offering_section_id': self.mapping.pk, 'employee_id': self.employee.pk,
            'assignment_role': 'TUTOR', 'workload_hours': '1', 'start_date':'2026-09-01',
            'end_date':'2026-09-30', 'reason':'Denied resource'}, format='json', HTTP_IDEMPOTENCY_KEY='limited')
        self.assertEqual(response.status_code, 404)

        response = client.post('/api/v1/timetable/commands/queue-job/', {
            'revision_id': self.revision.pk, 'expected_version': 1, 'seed': 0,
            'choices': [[{'course_offering_section_id': self.mapping.pk,
                'faculty_assignment_id': self.assignment.pk, 'room_id': self.room.pk,
                'time_slot_id': self.slot.pk, 'day_of_week': 1,
                'effective_from': '2026-09-01', 'effective_to': '2026-09-30'}]],
            'reason': 'Restricted resource'}, format='json', HTTP_IDEMPOTENCY_KEY='restricted-job')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(m.SolverJob.objects.exists())

    def test_cross_institution_permission_does_not_grant_scope(self):
        from django.contrib.auth.models import Permission
        user = get_user_model().objects.create_user(username='unscoped-planner')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='teaching_timetable', codename='manage_timetable'))
        client = self.client_for(user)
        self.assertEqual(client.get('/api/v1/timetable/revisions/').data['count'], 0)
        response = client.post('/api/v1/timetable/commands/create-revision/', {
            'offering_id':self.offering.pk,'name':'Foreign','reason':'No scope'},
            format='json', HTTP_IDEMPOTENCY_KEY='foreign')
        self.assertEqual(response.status_code, 404)
        from apps.organization.models import Institution, Campus, Department, Programme
        from apps.curriculum_catalog.models import CurriculumScheme
        from apps.term_registration.models import ProgrammeTermOffering
        from apps.tenancy.models import InstitutionModule, Membership, ScopeGrant
        other = Institution.objects.create(university=self.institution.university,
            institution_code='M8FOREIGN', institution_name='Other institution')
        campus = Campus.objects.create(institution=other, campus_code='M8F', campus_name='Other campus')
        department = Department.objects.create(campus=campus, department_code='M8F', department_name='Other department')
        programme = Programme.objects.create(department=department, programme_code='M8F',
            programme_name='Other programme', programme_level='UG', duration_semesters=6)
        from datetime import date
        scheme = CurriculumScheme.objects.create(programme=programme, scheme_code='M8F',
            scheme_name='Other scheme', regulation_year=2026, effective_from=date(2026,1,1), status='ACTIVE')
        offering = ProgrammeTermOffering.objects.create(academic_term=self.term, programme=programme,
            curriculum_scheme=scheme, semester=self.semester, status='ACTIVE', created_by=self.root, updated_by=self.root)
        InstitutionModule.objects.create(institution=other, teaching_timetable=True)
        ScopeGrant.objects.create(membership=Membership.objects.create(user=user, institution=other), role='INSTITUTION_ADMIN')
        own = client.post('/api/v1/timetable/commands/create-revision/', {
            'offering_id':offering.pk,'name':'Own scope','reason':'Authorized'},
            format='json', HTTP_IDEMPOTENCY_KEY='own-scope')
        self.assertEqual(own.status_code, 200, own.data)
        foreign = client.post('/api/v1/timetable/commands/create-revision/', {
            'offering_id':self.offering.pk,'name':'Foreign','reason':'Other institution'},
            format='json', HTTP_IDEMPOTENCY_KEY='foreign-with-grant')
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(client.get('/api/v1/timetable/revisions/').data['count'], 1)

    def test_historical_revision_survives_supersession(self):
        from apps.teaching_timetable import services as s
        self.session(); self.publish()
        original = self.revision
        self.revision = s.create_revision(actor=self.root, offering_id=self.offering.pk, name='Replacement', reason='New revision')
        self.session(); self.publish()
        original.refresh_from_db()
        self.assertEqual(original.status, 'SUPERSEDED')
        client = self.client_for(self.root)
        dates = '?date_from=2026-09-01&date_to=2026-09-30'
        history = client.get(f'/api/v1/timetable/revisions/{original.pk}/history/' + dates)
        self.assertEqual(len(history.data['results']), 4)
        self.assertEqual(len(client.get('/api/v1/timetable/occurrences/' + dates).data['results']), 4)
        workload = client.get('/api/v1/timetable/workload/' + dates)
        self.assertEqual(len(workload.data['actual']), 4)
        self.assertTrue(all(row['hours'] == '1.00' for row in workload.data['actual']))
        exported = client.get('/api/v1/timetable/workload/export/' + dates)
        self.assertEqual(exported.status_code, 200)
        self.assertIn(b'published', exported.content)
        availability = client.get(f'/api/v1/timetable/availability/{dates}&kind=room&resource_id={self.room.pk}')
        self.assertEqual(availability.status_code, 200, availability.data)
        self.assertEqual(len(availability.data['busy']), 4)

    def test_import_preview_reports_duplicate_source_ids_without_writes(self):
        csv = 'source_id,course_offering_section_id,employee_id,assignment_role,workload_hours,start_date,end_date\n'
        csv += f'x,{self.mapping.pk},{self.employee.pk},TUTOR,1,2026-09-01,2026-09-30\n' * 2
        count = m.FacultyAssignment.objects.count()
        response = self.client_for(self.root).post('/api/v1/timetable/import-allocations/',
            {'csv_text':csv,'reason':'Review import','dry_run':True}, format='json', HTTP_IDEMPOTENCY_KEY='import-preview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['conflicts']), 1)
        self.assertEqual(m.FacultyAssignment.objects.count(), count)
