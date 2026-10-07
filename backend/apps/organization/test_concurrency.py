from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from django.db import connections
from django.contrib.auth import get_user_model
from apps.common_reference.services import Conflict
from .models import University,OrganizationAudit
from .services import save_record

class OrganizationConcurrencyTests(TransactionTestCase):
    def test_concurrent_duplicate_creates_commit_one_record_and_one_event(self):
        root=get_user_model().objects.create_superuser(username='race-root',password='test')
        def create():
            try:
                actor=get_user_model().objects.get(pk=root.pk)
                save_record(University,{'university_code':'RACE','university_name':'Concurrent'},actor=actor)
                return 'created'
            except Conflict:
                return 'conflict'
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _:create(),range(2)))
        self.assertCountEqual(outcomes,['created','conflict'])
        self.assertEqual(University.objects.filter(university_code='RACE').count(),1)
        self.assertEqual(OrganizationAudit.objects.count(),1)
