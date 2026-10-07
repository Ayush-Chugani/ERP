from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date
from django.test import TransactionTestCase, override_settings
from django.db import close_old_connections
from apps.people_master import models as m
from apps.people_master.services import set_primary, version
from apps.people_master.exceptions import PeopleConflict
from .test_services import fixture, student, address


@override_settings(PEOPLE_MASTER_ENABLED=True)
class PeopleConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixture(self)

    def test_competing_primary_promotions(self):
        person = student(self)
        rows = [
            address(self, person, date(2026, 1, 1)),
            address(self, person, date(2026, 1, 1)),
        ]
        barrier = Barrier(2)

        def promote(row):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    set_primary(
                        m.StudentAddress,
                        row.pk,
                        actor=self.root,
                        expected_version="1",
                        reason="Select primary",
                    )
                    return "ok"
                except PeopleConflict:
                    return "conflict"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(promote, rows))
        self.assertCountEqual(results, ["ok", "conflict"])
        self.assertEqual(
            m.StudentAddress.objects.filter(
                student=person, is_primary=True, valid_to__isnull=True
            ).count(),
            1,
        )
