from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.research_proposals import services as s
from apps.research_proposals.models import ResearchProposal
from apps.staff_activities.models import ActivityCommandReceipt

from . import test_module


@override_settings(
    RESEARCH_PROPOSALS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConcurrentProposalTests(TransactionTestCase):
    def _fixture_teardown(self):
        # Production append-only triggers remain active during assertions.
        # TRUNCATE is used only to clean this isolated test's committed history.
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError(
                "Refusing test cleanup outside the isolated test database."
            )
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE platform_research_proposal_status_history")
        super()._fixture_teardown()

    def setUp(self):
        test_module.ProposalTests.setUp(self)

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
        self.assertEqual(ResearchProposal.objects.count(), 1)
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)
