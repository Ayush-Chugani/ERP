from .test_api import OrganizationAPITests
from .models import Campus,OrganizationAudit
from .bulk import safe_cell

class BulkTests(OrganizationAPITests):
    def test_import_dry_run_atomicity_and_export(self):
        content=f'institution_id,campus_code,campus_name\n{self.a.pk},MAIN,Main campus\n'
        response=self.client.post('/api/v1/organization/campuses/import/',{'csv':content,'dry_run':True},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(Campus.objects.exists())
        response=self.client.post('/api/v1/organization/campuses/import/',{'csv':content,'dry_run':False},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(Campus.objects.count(),1)
        response=self.client.get('/api/v1/organization/campuses/export/')
        self.assertEqual(response.status_code,200)
        self.assertIn('Main campus',response.content.decode())
        bad=f'institution_id,campus_code,campus_name\n{self.a.pk},NEW,New\n{self.b.pk},BAD,Bad\n'
        response=self.client.post('/api/v1/organization/campuses/import/',{'csv':bad,'dry_run':False},format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Campus.objects.filter(campus_code='NEW').exists())
        self.assertTrue(safe_cell('=HYPERLINK("bad")').startswith("'"))
