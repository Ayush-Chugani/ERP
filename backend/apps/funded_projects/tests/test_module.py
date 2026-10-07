from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as ApiValidationError

from apps.documents_exit.models import FileObject
from apps.documents_exit.tests.providers import pdf
from apps.funded_projects import services as s
from apps.funded_projects.models import (
    FundedResearchProject,
    ProjectStatusHistory,
    ResearchProjectFinancialUtilization,
    UtilizationVoid,
)
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink
from apps.research_proposals import services as proposals
from apps.research_proposals.tests import test_module as proposal_tests
from apps.staff_activities.models import ActivityAttachment, StaffActivity
from apps.staff_profile import models as refs


@override_settings(
    FUNDED_PROJECTS_ENABLED=True,
    RESEARCH_PROPOSALS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ProjectTests(TestCase):
    def setUp(self):
        proposal_tests.ProposalTests.setUp(self)
        for index, code in enumerate(
            ["SANCTIONED", "ONGOING", "COMPLETED", "CLOSED", "CANCELLED"], start=20
        ):
            refs.ResearchStatus.objects.get_or_create(
                status_code=code,
                defaults={
                    "pk": index,
                    "status_name": code.title(),
                    "is_terminal": code in {"CLOSED", "CANCELLED"},
                },
            )
        call_command("seed_funded_projects", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="FUNDED_PROJECTS."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.proposal_values = self.values
        self.values = {
            "project_title": "Synthetic award",
            "funding_agency_id": self.agency.pk,
            "funding_type_id": self.funding_type.pk,
            "sanction_date": "2026-01-01",
            "project_start_date": "2026-01-02",
            "project_end_date": "2027-12-31",
            "sanction_order_number": "SYN-1",
            "sanctioned_amount": "1000.00",
        }
        self.url = "/api/v1/funded-projects/activities/"

    def create(self, key="p1", **values):
        return s.save_activity(
            self.root, self.values | values, context=self.context, key=key
        )

    def entry(self, row, key="l1", **values):
        payload = {
            "financial_year": "2026-2027",
            "reporting_period_from": "2026-01-02",
            "reporting_period_to": "2026-01-31",
            "opening_balance": "0.00",
            "amount_received": "100.01",
            "expenditure_amount": "20.01",
            "closing_balance": "80.00",
        } | values
        return s.utilization(
            self.root,
            row.pk,
            payload,
            expected_version=s.version(row.pk),
            reason="Synthetic financial report",
            key=key,
        )

    def revoke(self, resource, action):
        iam.RolePermission.objects.filter(
            role=self.role,
            permission__permission_code=f"FUNDED_PROJECTS.{resource}.{action}",
        ).delete()

    def test_create_retry_and_scope_revocation(self):
        row = self.create()
        self.assertEqual(row.pk, self.create().pk)
        self.assertEqual(FundedResearchProject.objects.count(), 1)
        self.assertEqual(row.staff_activity.approval_status.status_code, "APPROVED")
        with self.assertRaises(s.Conflict):
            self.create(project_title="Different")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()

    def test_validation_atomic_and_protected_fields(self):
        for changes in [
            {"sanctioned_amount": "-1"},
            {"sanctioned_amount": 1.2},
            {"sanctioned_amount": "1.234"},
            {"sanctioned_amount": "NaN"},
            {"currency_code": "ZZZ"},
            {"amount_received": "10"},
            {"research_status_id": 20},
            {"project_start_date": "2025-01-01"},
            {"project_end_date": "2025-01-01"},
            {"duration_months": 0},
            {"completion_date": "2025-01-01"},
            {"sanction_order_number": " "},
            {"project_title": " "},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
            self.assertFalse(FundedResearchProject.objects.exists())
        with (
            patch.object(
                ProjectStatusHistory.objects,
                "create",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertFalse(StaffActivity.objects.exists())

    def test_ledger_decimal_reconciliation_and_rollback(self):
        row = self.create()
        self.entry(row)
        row.refresh_from_db()
        self.assertEqual(row.amount_received, Decimal("100.01"))
        self.assertEqual(row.amount_utilized, Decimal("20.01"))
        for changes in [
            {"closing_balance": "99.00"},
            {"financial_year": "2026-2028"},
            {"opening_balance": "1.00"},
            {"amount_received": "1001.00", "closing_balance": "980.99"},
            {"amount_received": 1.1},
            {"reporting_period_to": "2025-01-01"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.entry(row, key="bad", **changes)
        self.assertEqual(ResearchProjectFinancialUtilization.objects.count(), 1)
        row.refresh_from_db()
        self.assertEqual(row.amount_received, Decimal("100.01"))

    def test_overlap_continuity_edit_void_retention(self):
        row = self.create()
        self.entry(row)
        with self.assertRaises(ValidationError):
            self.entry(
                row, key="overlap", opening_balance="80.00", closing_balance="160.00"
            )
        self.entry(
            row,
            key="second",
            reporting_period_from="2026-02-01",
            reporting_period_to="2026-02-28",
            opening_balance="80.00",
            closing_balance="160.00",
        )
        first, last = ResearchProjectFinancialUtilization.objects.order_by("pk")
        with self.assertRaises(ValidationError):
            s.utilization(
                self.root,
                row.pk,
                {},
                utilization_id=first.pk,
                void=True,
                expected_version=s.version(row.pk),
                reason="Correction",
                key="void-first",
            )
        s.utilization(
            self.root,
            row.pk,
            {},
            utilization_id=last.pk,
            void=True,
            expected_version=s.version(row.pk),
            reason="Correction",
            key="void-last",
        )
        self.assertEqual(ResearchProjectFinancialUtilization.objects.count(), 2)
        self.assertEqual(UtilizationVoid.objects.count(), 1)
        row.refresh_from_db()
        self.assertEqual(row.amount_received, Decimal("100.01"))
        with self.assertRaises(ValidationError):
            s.utilization(
                self.root,
                row.pk,
                {},
                utilization_id=last.pk,
                expected_version=s.version(row.pk),
                reason="Correction",
                key="edit-void",
            )

    def test_version_and_currency_freeze(self):
        row = self.create()
        old = s.version(row.pk)
        self.entry(row)
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"project_title": "Other"},
                activity_id=row.pk,
                expected_version=old,
                reason="Correction",
            )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {"currency_code": "USD"},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
                reason="Correction",
            )

    def test_workflow_separate_permission_completion_and_archive(self):
        row = self.create()
        self.revoke("STATUS", "UPDATE")
        with self.assertRaises(PermissionDenied):
            s.workflow(self.root, row.pk, "start", "Begin", s.version(row.pk), "start")
        iam.RolePermission.objects.create(
            role=self.role,
            permission=iam.Permission.objects.get(
                permission_code="FUNDED_PROJECTS.STATUS.UPDATE"
            ),
        )
        s.workflow(self.root, row.pk, "start", "Begin", s.version(row.pk), "start")
        with self.assertRaises(ValidationError):
            s.workflow(
                self.root, row.pk, "complete", "Done", s.version(row.pk), "complete"
            )
        s.save_activity(
            self.root,
            {
                "completion_date": "2026-03-01",
                "project_outcomes": "Completed deliverables",
            },
            activity_id=row.pk,
            expected_version=s.version(row.pk),
            reason="Report",
        )
        s.workflow(self.root, row.pk, "complete", "Done", s.version(row.pk), "complete")
        s.workflow(self.root, row.pk, "close", "Close", s.version(row.pk), "close")
        with self.assertRaises(ValidationError):
            self.entry(row)
        s.archive(self.root, row.pk, s.version(row.pk))
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)
        self.assertEqual(ProjectStatusHistory.objects.count(), 4)

    def test_conversion_approved_matching_and_unique(self):
        proposal = proposals.save_activity(
            self.root, self.proposal_values, context=self.context, key="proposal"
        )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                self.values,
                context=self.context,
                source_id=proposal.pk,
                key="convert",
            )
        proposal.research_status = refs.ResearchStatus.objects.get(
            status_code="APPROVED"
        )
        proposal.save()
        parent = proposal.staff_activity
        parent.approval_status = refs.ApprovalStatus.objects.get(status_code="APPROVED")
        parent.save()
        values = {k: v for k, v in self.values.items() if k != "project_title"}
        row = s.save_activity(
            self.root,
            values,
            context=self.context,
            source_id=proposal.pk,
            key="convert",
        )
        self.assertEqual(row.project_title, proposal.proposal_title)
        self.assertNotEqual(row.pk, proposal.pk)
        self.assertEqual(row.source_proposal_activity_id, proposal.pk)
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                values,
                context=self.context,
                source_id=proposal.pk,
                key="convert-again",
            )

    def test_api_financial_redaction_and_permission_separation(self):
        row = self.create()
        self.entry(row)
        detail = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["amount_received"], "100.01")
        self.revoke("FINANCE", "READ")
        for path in [self.url, self.url + str(row.pk) + "/"]:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200, result.data)
            data = (
                result.data["results"][0] if "results" in result.data else result.data
            )
            self.assertNotIn("sanctioned_amount", data)
            self.assertNotIn("amount_received", data)
        self.assertEqual(
            self.client.get(self.url + str(row.pk) + "/utilization/").status_code, 403
        )
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertNotIn(
            "100.01", self.client.get(self.url + "export/").content.decode()
        )
        self.assertEqual(self.client.get(self.url + "?amount_min=1").data["count"], 0)

    def test_api_create_edit_finance_and_mass_assignment(self):
        response = self.client.post(
            self.url,
            {"activity": self.values, "context": self.context},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-create",
        )
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["staff_activity"]
        bad = self.client.patch(
            self.url + pk + "/",
            {
                "activity": {"amount_utilized": "200"},
                "version": response.data["version"],
                "reason": "Test",
            },
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        payload = {
            "values": {
                "financial_year": "2026-2027",
                "reporting_period_from": "2026-01-02",
                "reporting_period_to": "2026-01-31",
                "amount_received": "30.00",
                "closing_balance": "30.00",
            },
            "version": response.data["version"],
            "reason": "Report",
        }
        result = self.client.post(
            self.url + pk + "/utilization/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-ledger",
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["amount_received"], "30.00")
        self.assertEqual(
            self.client.post(
                self.url + pk + "/utilization/",
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="api-ledger",
            ).status_code,
            200,
        )

    def test_reports_exact_currency_and_no_double_count(self):
        row = self.create(sanctioned_amount="99999999999999.99")
        self.entry(row)
        result = self.client.get(self.url + "summary/")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(
            result.data["amounts_by_currency"][0]["amount"], "99999999999999.99"
        )
        self.assertEqual(result.data["amounts_by_currency"][0]["received"], "100.01")

    def test_native_constraints_and_retained_history(self):
        row = self.create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            FundedResearchProject.objects.filter(pk=row.pk).update(sanctioned_amount=-1)
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "DELETE FROM platform_funded_project_status_history WHERE project_id=%s",
                [row.pk],
            )
        self.assertEqual(ProjectStatusHistory.objects.count(), 1)

    def test_flags_seed_and_read_scope(self):
        call_command("seed_funded_projects", stdout=StringIO())
        self.assertEqual(
            iam.Permission.objects.filter(
                permission_code__startswith="FUNDED_PROJECTS."
            ).count(),
            10,
        )
        row = self.create()
        self.grant.delete()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)
        with override_settings(FUNDED_PROJECTS_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_scope_deny_self_and_export(self):
        row = self.create(project_title="=HYPERLINK(1)")
        response = self.client.get(self.url + "export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=HYPERLINK", response.content.decode())
        self.grant.scope_type = "DEPARTMENT"
        from apps.organization.models import Department

        self.grant.department = Department.objects.create(
            campus=self.campus, department_code="OTHER24", department_name="Other"
        )
        self.grant.save()
        with self.assertRaises(PermissionDenied):
            self.create(key="cross-scope-create")
        self.assertEqual(FundedResearchProject.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)
        self.grant.scope_type = "SELF"
        self.grant.department = None
        self.grant.save()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        AccountLink.objects.create(user=self.root, employee=self.employee)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        perm = iam.Permission.objects.get(
            permission_code="FUNDED_PROJECTS.ACTIVITY.READ"
        )
        iam.UserPermissionOverride.objects.create(
            user=self.root,
            permission=perm,
            permission_effect="DENY",
            justification="Synthetic deny test",
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    @override_settings(
        DOCUMENTS_EXIT_ENABLED=True,
        DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.clean",
    )
    def test_evidence_security_replacement_and_rollback(self):
        row = self.create()
        other = self.create(key="other")
        with (
            TemporaryDirectory() as directory,
            override_settings(
                DOCUMENTS_EXIT_INSTITUTIONS=[self.institution.pk],
                DOCUMENTS_STORAGE_ROOT=Path(directory),
            ),
        ):

            def upload(data=None, replaces=None):
                return s.upload_attachment(
                    actor=self.root,
                    pk=row.pk,
                    expected_version=s.version(row.pk),
                    upload=SimpleUploadedFile(
                        "evidence.pdf",
                        pdf() if data is None else data,
                        content_type="application/pdf",
                    ),
                    title="Completion",
                    category="SANCTION_ORDER",
                    replaces=replaces,
                )

            first = upload()
            second = upload(replaces=first.pk)
            self.assertEqual(second.replaces_id, first.pk)
            stream, file = s.download_attachment(
                actor=self.root, pk=row.pk, attachment_id=first.pk
            )
            stream.close()
            self.assertEqual(file.pk, first.file_object_id)
            with self.assertRaises(ActivityAttachment.DoesNotExist):
                s.download_attachment(
                    actor=self.root, pk=other.pk, attachment_id=first.pk
                )
            response = self.client.get(
                self.url + str(other.pk) + f"/evidence/{first.pk}/download/"
            )
            self.assertEqual(response.status_code, 404)
            count = FileObject.objects.count()
            with self.assertRaises(ApiValidationError):
                upload(b"not a pdf")
            self.assertEqual(FileObject.objects.count(), count)
            with (
                patch(
                    "apps.funded_projects.services.ActivityAttachment.objects.create",
                    side_effect=RuntimeError("synthetic rollback"),
                ),
                self.assertRaises(RuntimeError),
            ):
                upload()
            self.assertEqual(FileObject.objects.count(), count)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)
            self.grant.delete()
            with self.assertRaises(PermissionDenied):
                s.download_attachment(
                    actor=self.root, pk=row.pk, attachment_id=first.pk
                )

    @override_settings(FUNDED_PROJECTS_CURRENCIES=("INR", "USD"))
    def test_scoped_queries_do_not_grow_per_row_and_currency_totals(self):
        self.create()
        with CaptureQueriesContext(connection) as first:
            result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200)
        for index in range(3):
            self.create(key="extra-" + str(index), currency_code="USD")
        with CaptureQueriesContext(connection) as many:
            result = self.client.get(self.url)
        self.assertEqual(len(first), len(many))
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 4)
        self.assertEqual(
            len(self.client.get(self.url + "summary/").data["amounts_by_currency"]), 2
        )
        self.assertEqual(
            self.client.get(self.url + "?ordering=password").status_code, 400
        )
        self.assertEqual(
            self.client.get(self.url + "?project_from=bad").status_code, 400
        )

    def test_finance_edit_and_void_are_independent_permissions(self):
        row = self.create()
        self.entry(row)
        self.revoke("FINANCE", "UPDATE")
        with self.assertRaises(PermissionDenied):
            self.entry(row, key="denied")
        with self.assertRaises(PermissionDenied):
            s.save_activity(
                self.root,
                {"sanctioned_amount": "1200.00"},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
                reason="Change",
            )
        s.save_activity(
            self.root,
            {"project_title": "Revised title"},
            activity_id=row.pk,
            expected_version=s.version(row.pk),
            reason="Correction",
        )
        entry = ResearchProjectFinancialUtilization.objects.get(staff_activity=row)
        s.utilization(
            self.root,
            row.pk,
            {},
            utilization_id=entry.pk,
            void=True,
            expected_version=s.version(row.pk),
            reason="Correction",
            key="void-permitted",
        )
        self.assertEqual(UtilizationVoid.objects.count(), 1)

    def test_cross_project_ledger_and_audit_failure_leave_totals_unchanged(self):
        row = self.create()
        other = self.create(key="other")
        self.entry(row)
        entry = ResearchProjectFinancialUtilization.objects.get(staff_activity=row)
        result = self.client.post(
            self.url + str(other.pk) + "/utilization/",
            {
                "utilization_id": str(entry.pk),
                "void": True,
                "version": s.version(other.pk),
                "reason": "Cross-record attempt",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="cross",
        )
        self.assertEqual(result.status_code, 404)
        with (
            patch(
                "apps.funded_projects.services.record",
                side_effect=RuntimeError("audit failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            s.utilization(
                self.root,
                row.pk,
                {},
                utilization_id=entry.pk,
                void=True,
                expected_version=s.version(row.pk),
                reason="Correction",
                key="void-fail",
            )
        row.refresh_from_db()
        self.assertEqual(row.amount_received, Decimal("100.01"))
        self.assertFalse(UtilizationVoid.objects.exists())

    def test_source_prefill_requires_proposal_and_finance_scope(self):
        proposal = proposals.save_activity(
            self.root, self.proposal_values, context=self.context, key="proposal"
        )
        proposal.research_status = refs.ResearchStatus.objects.get(
            status_code="APPROVED"
        )
        proposal.save()
        parent = proposal.staff_activity
        parent.approval_status = refs.ApprovalStatus.objects.get(status_code="APPROVED")
        parent.save()
        path = "/api/v1/funded-projects/lookups/proposal-prefill/?source_id=" + str(
            proposal.pk
        )
        result = self.client.get(path)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertNotIn("sanctioned_amount", result.data)
        self.assertEqual(result.data["project_title"], proposal.proposal_title)
        self.revoke("FINANCE", "READ")
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_adoption_and_reverse_guards_are_nondestructive(self):
        from importlib import import_module
        from unittest.mock import Mock

        migration = import_module("apps.funded_projects.migrations.0001_initial")
        with self.assertRaises(RuntimeError):
            migration.install(None, connection.schema_editor())
        row = self.create()
        editor = Mock(connection=connection)
        editor.quote_name = connection.ops.quote_name
        with self.assertRaises(RuntimeError):
            migration.guard_reverse(None, editor)
        editor.execute.assert_not_called()
        self.assertTrue(FundedResearchProject.objects.filter(pk=row.pk).exists())

    def test_financial_audit_is_scoped_and_retains_exact_before_after(self):
        row = self.create()
        s.utilization(
            self.root,
            row.pk,
            {
                "financial_year": "2026-2027",
                "reporting_period_from": "2026-01-02",
                "reporting_period_to": "2026-01-31",
                "amount_received": "33.33",
                "closing_balance": "33.33",
            },
            expected_version=s.version(row.pk),
            reason="Receipt reconciled",
            key="audit-entry",
            request_id="synthetic-correlation",
        )
        path = self.url + str(row.pk) + "/financial-history/"
        result = self.client.get(path)
        self.assertEqual(result.status_code, 200, result.data)
        entry = result.data["results"][0]
        self.assertEqual(entry["after_values"]["amount_received"], "33.33")
        self.assertEqual(entry["request_identifier"], "synthetic-correlation")
        self.assertEqual(entry["details"]["reason"], "Receipt reconciled")
        self.revoke("FINANCE", "READ")
        self.assertEqual(self.client.get(path).status_code, 403)
