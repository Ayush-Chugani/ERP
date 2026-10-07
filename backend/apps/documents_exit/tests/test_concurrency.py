from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.apps import apps
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings

from apps.documents_exit import models as m
from apps.documents_exit import services as s
from apps.documents_exit.migrations._canonical import install, retain

from . import test_exit as exits
from . import test_services as fixtures


def parallel(fn):
    barrier = Barrier(2)

    def worker(n):
        close_old_connections()
        try:
            barrier.wait(timeout=15)
            return fn(n)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        return [
            future.result(timeout=45)
            for future in [pool.submit(worker, 0), pool.submit(worker, 1)]
        ]


@override_settings(
    DOCUMENTS_EXIT_ENABLED=True,
    DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.clean",
    DOCUMENTS_CERTIFICATE_RENDERER="apps.documents_exit.tests.providers.pdf",
)
class IssuanceTests(TransactionTestCase):
    setUp = fixtures.DocumentTests.setUp
    request = fixtures.DocumentTests.request
    approved = fixtures.DocumentTests.approved

    def test_concurrent_issue_creates_one_file(self):
        obj = self.approved()
        results = parallel(
            lambda n: (
                s.issue_certificate(
                    actor=self.root, pk=obj.pk, reason="Concurrent issue"
                ).file_object_id
            )
        )
        self.assertEqual(results[0], results[1])
        self.assertEqual(m.FileObject.objects.count(), 1)

    def test_concurrent_request_numbers_unique(self):
        with override_settings(
            DOCUMENTS_EXIT_POLICIES={
                str(self.institution.pk): {"allow_concurrent_requests": True}
            }
        ):
            results = parallel(lambda n: self.request().request_number)
        self.assertEqual(len(set(results)), 2)

    def test_reverse_retains_then_readopts_data(self):
        obj = self.request()
        # Exercise M13's own callbacks without reversing downstream modules.
        # M14 owns non-reversible recipient mappings and deliberately blocks a graph rollback.
        with connection.schema_editor() as editor:
            retain(apps, editor)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM certificate_request WHERE certificate_request_id=%s",
                [obj.pk],
            )
            self.assertEqual(cursor.fetchone()[0], 1)
        with connection.schema_editor() as editor:
            install(apps, editor)
        self.assertTrue(m.CertificateRequest.objects.filter(pk=obj.pk).exists())


@override_settings(
    DOCUMENTS_EXIT_ENABLED=True,
    ADMISSION_ENROLMENT_ENABLED=True,
    PEOPLE_MASTER_ENABLED=True,
    TERM_REGISTRATION_ENABLED=True,
    DOCUMENTS_EXIT_CLEARANCE="apps.documents_exit.tests.providers.cleared",
)
class ExitRaceTests(TransactionTestCase):
    setUp = exits.ExitTests.setUp
    finalize = exits.ExitTests.finalize

    def test_concurrent_identical_finalization_creates_one_exit(self):
        results = parallel(lambda n: self.finalize().pk)
        self.assertEqual(results[0], results[1])
        self.assertEqual(m.StudentExit.objects.count(), 1)
