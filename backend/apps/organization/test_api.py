from django.core.cache import cache
from rest_framework.test import APIClient
from .test_services import OrganizationServiceTests
from .models import Campus,Department
from apps.tenancy.models import ScopeGrant

class OrganizationAPITests(OrganizationServiceTests):
    def setUp(self):
        super().setUp();cache.clear()
        self.client=APIClient();self.client.force_authenticate(self.user)
    def test_api_scope_lifecycle_and_constraints(self):
        response=self.client.get('/api/v1/organization/institutions/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.get(f'/api/v1/organization/institutions/{self.b.pk}/').status_code,404)
        response=self.client.post('/api/v1/organization/campuses/',{'institution_id':self.a.pk,'campus_code':' north ','campus_name':'North'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        pk=response.data['campus_id']
        self.assertEqual(response.data['campus_code'],'NORTH')
        self.assertEqual(self.client.post(f'/api/v1/organization/campuses/{pk}/deactivate/').status_code,200)
        self.assertEqual(self.client.post(f'/api/v1/organization/campuses/{pk}/reactivate/').status_code,200)
        self.assertEqual(self.client.delete(f'/api/v1/organization/campuses/{pk}/').status_code,405)
        self.assertEqual(self.client.patch(f'/api/v1/organization/campuses/{pk}/',{'created_at':'bad'},format='json').status_code,400)
        self.assertEqual(self.client.post('/api/v1/organization/campuses/',{'institution_id':self.b.pk,'campus_code':'X','campus_name':'Bad'},format='json').status_code,400)
    def test_department_scope_does_not_expose_siblings_or_buildings(self):
        campus=Campus.objects.create(institution=self.a,campus_code='C',campus_name='Campus')
        dept=Department.objects.create(campus=campus,department_code='D',department_name='Dept')
        Department.objects.create(campus=campus,department_code='E',department_name='Other')
        self.grant.role='DEPARTMENT_ADMIN';self.grant.campus=campus;self.grant.department=dept;self.grant.full_clean();self.grant.save()
        self.assertEqual(self.client.get('/api/v1/organization/departments/').data['count'],1)
        self.assertEqual(self.client.get('/api/v1/organization/buildings/').data['count'],0)
        self.assertEqual(self.client.patch(f'/api/v1/organization/campuses/{campus.pk}/',{'campus_name':'Attack'},format='json').status_code,404)
