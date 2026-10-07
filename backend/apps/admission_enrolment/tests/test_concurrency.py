from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from . import test_services as fixtures
from apps.admission_enrolment import models as m, services as s


@override_settings(ADMISSION_ENROLMENT_ENABLED=True, PEOPLE_MASTER_ENABLED=True)
class AdmissionConcurrencyTests(TransactionTestCase):
    setUp=fixtures.AdmissionTests.setUp

    def test_simultaneous_retries_commit_one_enrolment(self):
        s.record_clearance(actor=self.root,pk=self.application.pk,version=self.application.version,reference='RACE')
        def run():
            close_old_connections()
            try:
                return s.admit_application(actor=self.root,application_id=self.application.pk,
                    version=self.application.version,payload=self.payload,idempotency_key='same-key').pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)]
            ids=[future.result(timeout=30) for future in futures]
        self.assertEqual(ids[0],ids[1])
        self.assertEqual(m.StudentProgrammeEnrolment.objects.count(),1)
        self.assertEqual(m.CommandReceipt.objects.count(),1)
