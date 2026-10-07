from .test_api import OrganizationAPITests
from .models import Campus

class SnapshotSecurityTests(OrganizationAPITests):
    def test_snapshot_is_scoped_bounded_and_excludes_contacts(self):
        response=self.client.get('/api/v1/organization/institutions/offline-snapshot/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['user_id'],self.user.pk)
        self.assertEqual(len(response.data['records']),1)
        self.assertEqual(response.data['records'][0]['institution_id'],self.a.pk)
        self.assertNotIn('email',response.data['records'][0])
        self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(self.client.get('/api/v1/organization/institutions/offline-snapshot/?is_active=all').status_code,400)
        self.assertEqual(self.client.get('/api/v1/organization/institutions/?page=invalid').status_code,400)
        self.module.organization_structure=False;self.module.save()
        self.assertEqual(self.client.get('/api/v1/organization/institutions/offline-snapshot/').data['records'],[])
