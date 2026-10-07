from django.core.cache import cache
from django.db import connection,transaction,IntegrityError
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test.utils import CaptureQueriesContext
from .catalogue import RESOURCES
from .models import University,Institution,Campus,Department,Programme,ProgrammeSpecialization,Building,Room,OrganizationAudit

class FullHierarchyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.root=get_user_model().objects.create_superuser(username='all-resources',password='test')
        self.client=APIClient();self.client.force_authenticate(self.root)
    def test_eight_resource_workflow_and_query_bound(self):
        ids={}
        for r in RESOURCES:
            payload={}
            for field in r.model._meta.fields:
                if field.primary_key or field.name in ('created_at','updated_at','is_active'):continue
                if field.name=='state':continue
                if field.is_relation:payload[field.attname]=ids[field.related_model]
                elif field.choices:payload[field.name]=field.choices[0][0]
                elif field.name=='duration_semesters':payload[field.name]=6
                elif field.name=='maximum_duration_semesters':payload[field.name]=10
                elif field.name=='capacity':payload[field.name]=40
                elif not field.blank:payload[field.name]='EXAMPLE' if field.name.endswith('_code') else 'Example name'
            response=self.client.post(f'/api/v1/organization/{r.path}/',payload,format='json')
            self.assertEqual(response.status_code,201,response.data)
            pk=response.data[r.model._meta.pk.name];ids[r.model]=pk
            with CaptureQueriesContext(connection) as queries:
                listed=self.client.get(f'/api/v1/organization/{r.path}/')
                self.assertEqual(listed.status_code,200,listed.data)
                self.assertEqual(listed.data['count'],1)
            self.assertLessEqual(len(queries),5,'List queries must not grow with parent depth')
            self.assertEqual(self.client.get(f'/api/v1/organization/{r.path}/{pk}/').status_code,200)
            self.assertEqual(self.client.post(f'/api/v1/organization/{r.path}/{pk}/deactivate/').status_code,200)
            self.assertEqual(self.client.post(f'/api/v1/organization/{r.path}/{pk}/reactivate/').status_code,200)
        self.assertEqual(OrganizationAudit.objects.count(),24)
        response=self.client.get(f'/api/v1/organization/programmes/?institution_id={ids[Institution]}&campus_id={ids[Campus]}')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.get('/api/v1/organization/programmes/?institution_id=1.5').status_code,400)
        self.assertEqual(self.client.get('/api/v1/organization/programmes/?institution_id=65536').status_code,400)
        for model in (University,Institution,Campus,Department,Programme,ProgrammeSpecialization,Building,Room):
            with connection.cursor() as cur:
                cur.execute('SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s',[model._meta.db_table,model._meta.pk.column])
                self.assertIn('unsigned',cur.fetchone()[0])
        with self.assertRaises(IntegrityError),transaction.atomic():
            Programme.objects.filter(pk=ids[Programme]).update(duration_semesters=0)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Room.objects.filter(pk=ids[Room]).update(capacity=0)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Room.objects.filter(pk=ids[Room]).update(room_type='INVALID')
