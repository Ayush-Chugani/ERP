from django.core.exceptions import ValidationError
from apps.tenancy.models import ScopeGrant,Membership
from .test_api import OrganizationAPITests
from .models import Campus,Department

class AuthorizationRegressionTests(OrganizationAPITests):
    def test_teacher_active_only_and_record_allowlist(self):
        campus=Campus.objects.create(institution=self.a,campus_code='A',campus_name='A')
        Campus.objects.create(institution=self.a,campus_code='B',campus_name='B')
        self.grant.role='TEACHER';self.grant.record_limits={'campuses':[campus.pk]};self.grant.full_clean();self.grant.save()
        response=self.client.get('/api/v1/organization/campuses/')
        self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.patch(f'/api/v1/organization/campuses/{campus.pk}/',{'campus_name':'No'},format='json').status_code,404)
        campus.is_active=False;campus.save()
        self.assertEqual(self.client.get(f'/api/v1/organization/campuses/{campus.pk}/').status_code,404)
        self.assertEqual(self.client.get('/api/v1/organization/campuses/?is_active=all').status_code,403)
    def test_cross_tenant_scope_grants_fail_validation(self):
        campus=Campus.objects.create(institution=self.b,campus_code='B',campus_name='B')
        grant=ScopeGrant(membership=self.member,role='CAMPUS_ADMIN',campus=campus)
        with self.assertRaises(ValidationError):grant.full_clean()
        # Even a bypassing writer cannot widen scope: selectors validate the join.
        grant.save()
        self.grant.is_active=False;self.grant.save()
        self.assertEqual(self.client.get('/api/v1/organization/campuses/').data['count'],0)
    def test_scoped_impact_and_historical_move_rejection(self):
        campus=Campus.objects.create(institution=self.a,campus_code='A',campus_name='A')
        other=Campus.objects.create(institution=self.a,campus_code='B',campus_name='B')
        dept=Department.objects.create(campus=campus,department_code='D',department_name='D')
        impact=self.client.get(f'/api/v1/organization/institutions/{self.a.pk}/impact/')
        self.assertEqual(impact.status_code,200)
        self.assertFalse(any('tenancy' in name for name in impact.data['references']))
        response=self.client.post(f'/api/v1/organization/departments/{dept.pk}/move/',{'campus_id':other.pk},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['campus_id'],other.pk)
        response=self.client.post(f'/api/v1/organization/campuses/{other.pk}/move/',{'institution_id':self.b.pk},format='json')
        self.assertIn(response.status_code,[400,403,409])
    def test_metadata_defaults_and_export_template(self):
        response=self.client.get('/api/v1/organization/metadata/')
        self.assertEqual(response.status_code,200)
        university=next(r for r in response.data['resources'] if r['path']=='universities')
        self.assertEqual(next(f for f in university['fields'] if f['name']=='university_type')['default'],'OTHER')
        template=self.client.get('/api/v1/organization/campuses/import-template/')
        self.assertEqual(template.status_code,200)
        self.assertNotIn('created_at',template.content.decode())

    def test_tenant_list_query_count_does_not_grow_with_rows(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        campus=Campus.objects.create(institution=self.a,campus_code='PERF',campus_name='Performance')
        Department.objects.create(campus=campus,department_code='D0',department_name='Dept 0')
        with CaptureQueriesContext(connection) as first:
            self.assertEqual(self.client.get('/api/v1/organization/departments/').status_code,200)
        for number in range(1,12):Department.objects.create(campus=campus,department_code=f'D{number}',department_name=f'Dept {number}')
        with CaptureQueriesContext(connection) as many:
            response=self.client.get('/api/v1/organization/departments/')
            self.assertEqual(response.data['count'],12)
        self.assertLessEqual(len(many),len(first)+1)
