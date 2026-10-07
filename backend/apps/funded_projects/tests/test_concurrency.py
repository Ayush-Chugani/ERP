from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from apps.funded_projects import services as s
from apps.funded_projects.models import (
    FundedResearchProject,
    ResearchProjectFinancialUtilization,
)
from apps.identity_access.models import UserRoleAssignment

from . import test_module


@override_settings(
    FUNDED_PROJECTS_ENABLED=True,
    RESEARCH_PROPOSALS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConcurrentProjects(TransactionTestCase):
    def setUp(self):
        test_module.ProjectTests.setUp(self)

    def _fixture_teardown(self):
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError("Isolated test database required")
        with connection.cursor() as cursor:
            for table in [
                "platform_funded_project_status_history",
                "platform_research_utilization_void",
                "platform_research_proposal_status_history",
            ]:
                cursor.execute("TRUNCATE TABLE " + table)
        super()._fixture_teardown()

    def test_concurrent_financial_changes_do_not_lose_receipts(self):
        row = s.save_activity(
            self.root, self.values, context=self.context, key="project"
        )
        other = get_user_model().objects.create_user(username="finance2")
        UserRoleAssignment.objects.create(
            user=other,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=self.grant.valid_from,
        )
        expected = s.version(row.pk)
        barrier = Barrier(2)

        def write(actor_id):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    s.utilization(
                        actor,
                        row.pk,
                        {
                            "financial_year": "2026-2027",
                            "reporting_period_from": "2026-01-02",
                            "reporting_period_to": "2026-01-31",
                            "opening_balance": "0.00",
                            "amount_received": "99.99",
                            "expenditure_amount": "0.00",
                            "closing_balance": "99.99",
                        },
                        expected_version=expected,
                        reason="Concurrent report",
                        key="report",
                    )
                    return "saved"
                except s.Conflict:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(write, user.pk) for user in [self.root, other]]
            results = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(ResearchProjectFinancialUtilization.objects.count(), 1)
        self.assertEqual(
            str(FundedResearchProject.objects.get(pk=row.pk).amount_received), "99.99"
        )

    def test_simultaneous_conversion_creates_only_one_project(self):
        from apps.research_proposals import services as proposals
        from apps.staff_profile.models import ApprovalStatus, ResearchStatus

        proposal = proposals.save_activity(
            self.root, self.proposal_values, context=self.context, key="proposal-source"
        )
        proposal.research_status = ResearchStatus.objects.get(status_code="APPROVED")
        proposal.save()
        parent = proposal.staff_activity
        parent.approval_status = ApprovalStatus.objects.get(status_code="APPROVED")
        parent.save()
        other = get_user_model().objects.create_user(username="converter2")
        UserRoleAssignment.objects.create(
            user=other,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=self.grant.valid_from,
        )
        barrier = Barrier(2)

        def convert(actor_id):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    s.save_activity(
                        actor,
                        self.values,
                        context=self.context,
                        source_id=proposal.pk,
                        key="convert",
                    )
                    return "saved"
                except s.Conflict:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(convert, user.pk) for user in [self.root, other]]
            results = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(
            FundedResearchProject.objects.filter(
                source_proposal_activity=proposal
            ).count(),
            1,
        )
