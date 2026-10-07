from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.faculty_internships import services as s
from apps.faculty_internships.models import FacultyInternship
from apps.staff_activities.models import ActivityCommandReceipt

from . import test_module


@override_settings(
    FACULTY_INTERNSHIPS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConcurrentInternshipTests(TransactionTestCase):
    def setUp(self):
        test_module.InternshipTests.setUp(self)

    def test_simultaneous_creation_reuses_one_parent_and_receipt(self):
        barrier = Barrier(2)

        def create():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.root.pk)
                barrier.wait(timeout=10)
                return s.save_activity(
                    actor, self.values, context=self.context, key="parallel-create"
                ).pk
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(create) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(FacultyInternship.objects.count(), 1)
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)
