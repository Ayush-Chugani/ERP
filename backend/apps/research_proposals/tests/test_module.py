from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
)
from rest_framework.exceptions import (
    ValidationError as ApiValidationError,
)
from rest_framework.test import APIClient

from apps.documents_exit.models import FileObject
from apps.documents_exit.tests.providers import pdf
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink, Employee, EmployeeAssignment
from apps.people_master.tests.test_services import fixture
from apps.research_proposals import services as s
from apps.research_proposals.models import (
    ResearchProposal,
    ResearchProposalStatusHistory,
)
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_profile import models as refs


@override_settings(
    RESEARCH_PROPOSALS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ProposalTests(TestCase):
    def setUp(self):
        fixture(self)
        self.employee = Employee.objects.create(
            institution=self.institution,
            employment_source=self.source,
            employee_number="M25-SYNTHETIC",
            first_name="Synthetic",
            display_name="Synthetic",
            joining_date=date(2020, 1, 1),
            employment_type="REGULAR",
            employment_status="ACTIVE",
        )
        for index, code in enumerate(
            [
                "DRAFT",
                "SUBMITTED",
                "UNDER_REVIEW",
                "RETURNED",
                "VERIFIED",
                "APPROVED",
                "REJECTED",
                "WITHDRAWN",
            ],
            start=1,
        ):
            refs.ApprovalStatus.objects.get_or_create(
                status_code=code,
                defaults={
                    "pk": index,
                    "status_name": code.title(),
                    "is_terminal": code in {"APPROVED", "REJECTED", "WITHDRAWN"},
                },
            )
        for index, code in enumerate(["PENDING", "VERIFIED"], start=1):
            refs.VerificationStatus.objects.get_or_create(
                status_code=code,
                defaults={
                    "pk": index,
                    "status_name": code.title(),
                    "is_terminal": code == "VERIFIED",
                },
            )
        from apps.identity_access.seeding import catalogue

        for index, values in enumerate(catalogue()["actions"], start=1):
            iam.AccessAction.objects.get_or_create(
                action_code=values["action_code"], defaults={"pk": index, **values}
            )
        for index, code in enumerate(
            [
                "DRAFT",
                "SUBMITTED",
                "UNDER_REVIEW",
                "RETURNED",
                "VERIFIED",
                "APPROVED",
                "REJECTED",
                "WITHDRAWN",
            ],
            start=1,
        ):
            refs.ResearchStatus.objects.get_or_create(
                status_code=code,
                defaults={
                    "pk": index,
                    "status_name": code.title(),
                    "is_terminal": code in {"APPROVED", "REJECTED", "WITHDRAWN"},
                },
            )
        call_command("seed_research_proposals", stdout=StringIO())
        self.assignment = EmployeeAssignment.objects.create(
            employee=self.employee,
            campus=self.campus,
            department=self.department,
            designation=self.designation,
            start_date=date(2020, 1, 1),
        )
        self.organization = refs.ExternalOrganization.objects.create(
            organization_name="Synthetic industry"
        )
        self.funding_type = refs.FundingType.objects.create(
            pk=1,
            funding_type_code="TEST",
            funding_type_name="Synthetic",
            is_external=True,
        )
        self.agency = refs.FundingAgency.objects.create(
            organization=self.organization, funding_type=self.funding_type
        )
        self.role = iam.Role.objects.create(
            role_code="M25_TEST",
            role_name="M25 test",
            role_category="SYSTEM",
            role_level="GLOBAL",
        )
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="RESEARCH_PROPOSALS."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.grant = iam.UserRoleAssignment.objects.create(
            user=self.root,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.context = {
            "employee_assignment_id": self.assignment.pk,
            "context_date": "2026-01-01",
        }
        self.values = {
            "funding_agency_id": self.agency.pk,
            "funding_type_id": self.funding_type.pk,
            "proposal_submission_date": date(2026, 1, 2),
            "proposal_title": "Synthetic proposal",
        }
        self.client = APIClient()
        self.client.force_authenticate(self.root)
        self.url = "/api/v1/research-proposals/activities/"

    def create(self, key="create-1", **values):
        return s.save_activity(
            self.root, self.values | values, context=self.context, key=key
        )

    def reviewer(self):
        user = get_user_model().objects.create_user(username="m25reviewer")
        iam.UserRoleAssignment.objects.create(
            user=user,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        return user

    def test_atomic_create_retry_collision_and_revoke(self):
        row = self.create()
        self.assertEqual(self.create().pk, row.pk)
        self.assertEqual(ResearchProposal.objects.count(), 1)
        self.assertEqual(
            row.staff_activity.activity_type.activity_type_code, s.TYPE_CODE
        )
        with self.assertRaises(s.Conflict):
            self.create(proposal_title="changed")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)

    def test_validation_and_rollback(self):
        for values in [
            {"proposal_title": " "},
            {"principal_investigator_employee_id": 999},
            {"currency_code": "R1"},
            {"requested_amount": Decimal(-1)},
            {"review_comments": "Injected"},
            {"staff_activity_id": 999},
            {"funding_agency_id": 999},
        ]:
            before = StaffActivity.objects.count()
            with self.assertRaises((ValidationError, NotFound)):
                self.create(**values)
            self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(ActivityCommandReceipt.objects.count(), 0)
        row = self.create(requested_amount=Decimal(25), currency_code="usd")
        self.assertEqual(row.requested_amount, Decimal(25))
        self.assertEqual(row.currency_code, "USD")

    def test_invalid_dates_assignment_and_inactive_master(self):
        self.context["context_date"] = "2019-01-01"
        with self.assertRaises(ValidationError):
            self.create()
        self.context["context_date"] = "2026-01-01"
        self.assignment.end_date = date(2025, 1, 1)
        self.assignment.save()
        with self.assertRaises(ValidationError):
            self.create()
        self.assignment.end_date = None
        self.assignment.save()
        self.organization.is_active = False
        self.organization.save()
        with self.assertRaises(ValidationError):
            self.create()

    def test_update_version_and_protected_context(self):
        row = self.create()
        token = s.version(row.pk)
        s.save_activity(
            self.root,
            {"proposal_title": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"proposal_title": "stale"},
                activity_id=row.pk,
                expected_version=token,
            )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {},
                context=self.context,
                activity_id=row.pk,
                expected_version=s.version(row.pk),
            )

    def test_workflow_independence_idempotence_and_terminal_edits(self):
        row = self.create()
        token = s.version(row.pk)
        s.workflow(self.root, row.pk, "submit", "", token, "submit-1")
        s.workflow(self.root, row.pk, "submit", "", token, "submit-1")
        with self.assertRaises(PermissionDenied):
            s.workflow(
                self.root, row.pk, "verify", "ok", s.version(row.pk), "verify-self"
            )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {"proposal_title": "No"},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
            )
        reviewer = self.reviewer()
        with self.assertRaises(ValidationError):
            s.workflow(reviewer, row.pk, "approve", "ok", s.version(row.pk), "early")
        s.workflow(reviewer, row.pk, "review", "", s.version(row.pk), "review-1")
        s.workflow(
            reviewer, row.pk, "return", "Correct dates", s.version(row.pk), "return-1"
        )
        s.save_activity(
            self.root,
            {"proposal_title": "Corrected"},
            activity_id=row.pk,
            expected_version=s.version(row.pk),
        )
        s.workflow(self.root, row.pk, "submit", "", s.version(row.pk), "submit-2")
        s.workflow(
            reviewer,
            row.pk,
            "verify",
            "Evidence checked",
            s.version(row.pk),
            "verify-1",
        )
        s.workflow(
            reviewer, row.pk, "approve", "Approved", s.version(row.pk), "approve-1"
        )
        row.staff_activity.refresh_from_db()
        self.assertEqual(row.staff_activity.approval_status.status_code, "APPROVED")
        with self.assertRaises(ValidationError):
            s.archive(self.root, row.pk, s.version(row.pk))

    def test_api_crud_unknown_fields_history_archive(self):
        response = self.client.post(
            self.url,
            {"context": self.context, "activity": self.values},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-create",
        )
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["staff_activity"]
        self.assertIsInstance(pk, str)
        self.assertTrue(response.data["can_edit"])
        self.assertEqual(len(response.data["history"]), 1)
        self.assertEqual(response.data["history"][0]["to_status"], "DRAFT")
        self.assertIn("changed_at", response.data["history"][0])
        response = self.client.patch(
            self.url + pk + "/",
            {
                "version": response.data["version"],
                "activity": {"approval_status_id": 99},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        response = self.client.get(self.url + pk + "/")
        response = self.client.delete(
            self.url + pk + "/", {"version": response.data["version"]}, format="json"
        )
        self.assertEqual(response.status_code, 204, response.data)
        self.assertEqual(self.client.get(self.url + pk + "/").status_code, 404)
        self.assertTrue(ResearchProposal.objects.filter(pk=pk).exists())

    def test_scope_deny_self_and_export(self):
        row = self.create(proposal_title="=HYPERLINK(1)")
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
        self.assertEqual(ResearchProposal.objects.count(), 1)
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
            permission_code="RESEARCH_PROPOSALS.ACTIVITY.READ"
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

    def test_filters_reports_and_constant_list_queries(self):
        self.create(requested_amount=Decimal(20))
        with CaptureQueriesContext(connection) as first:
            self.client.get(self.url)
        for i in range(4):
            self.create(
                key=f"create-{i + 2}",
                requested_amount=Decimal(3),
                currency_code="USD",
            )
        with CaptureQueriesContext(connection) as later:
            self.client.get(self.url)
        self.assertEqual(len(first), len(later))
        self.assertEqual(
            self.client.get(self.url, {"currency": "INR"}).data["count"], 1
        )
        self.assertEqual(
            self.client.get(self.url, {"ordering": "password"}).status_code, 400
        )
        self.assertEqual(
            self.client.get(self.url, {"date_from": "nonsense"}).status_code, 400
        )
        summary = self.client.get(self.url + "summary/").data
        self.assertEqual(summary["count"], 5)
        self.assertEqual(len(summary["amounts_by_currency"]), 2)
        self.assertEqual(
            self.client.get(
                "/api/v1/research-proposals/lookups/assignments/"
            ).status_code,
            200,
        )

    def test_native_schema_and_database_constraint(self):
        row = self.create()
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE research_proposal")
            ddl = cursor.fetchone()[1].lower()
            for fragment in [
                "bigint unsigned",
                "decimal(16,2)",
                "char(3)",
                "chk_research_proposal_requested_amount",
                "fk_research_proposal_activity",
                "utf8mb4_unicode_ci",
            ]:
                self.assertIn(fragment, ddl)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ResearchProposal.objects.filter(pk=row.pk).update(requested_amount=-1)

    def test_configuration_idempotency_missing_and_disabled(self):
        count = iam.UserRoleAssignment.objects.count()
        call_command("seed_research_proposals", stdout=StringIO())
        call_command("seed_research_proposals", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        refs.ApprovalStatus.objects.filter(status_code="DRAFT").update(is_active=False)
        with self.assertRaises(ValidationError):
            self.create()
        with override_settings(RESEARCH_PROPOSALS_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)

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
                    category="PROPOSAL",
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
                    "apps.research_proposals.services.ActivityAttachment.objects.create",
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

    def test_noop_and_reverted_edits_still_invalidate_versions(self):
        row = self.create()
        original = s.version(row.pk)
        s.save_activity(
            self.root,
            {"proposal_title": "Changed"},
            activity_id=row.pk,
            expected_version=original,
        )
        s.save_activity(
            self.root,
            {"proposal_title": self.values["proposal_title"]},
            activity_id=row.pk,
            expected_version=s.version(row.pk),
        )
        self.assertNotEqual(original, s.version(row.pk))
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root, {}, activity_id=row.pk, expected_version=original
            )

    def test_audit_failure_rolls_back_parent_child_and_receipt(self):
        before = StaffActivity.objects.count()
        with (
            patch(
                "apps.research_proposals.services.record",
                side_effect=RuntimeError("synthetic"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(ResearchProposal.objects.count(), 0)
        self.assertEqual(ActivityCommandReceipt.objects.count(), 0)

    def test_api_workflow_retries_and_stale_patch(self):
        row = self.create()
        path = self.url + str(row.pk) + "/"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.data)
        payload = {"action": "submit", "version": response.data["version"]}
        first = self.client.post(
            path + "workflow/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-submit",
        )
        self.assertEqual(first.status_code, 200, first.data)
        again = self.client.post(
            path + "workflow/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-submit",
        )
        self.assertEqual(again.status_code, 200, again.data)
        self.assertEqual(again.data["status"], "SUBMITTED")
        self.assertEqual(
            self.client.patch(
                path,
                {
                    "activity": {"proposal_title": "stale"},
                    "version": payload["version"],
                },
                format="json",
            ).status_code,
            409,
        )

    @override_settings(
        DOCUMENTS_EXIT_ENABLED=True,
        DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.clean",
    )
    def test_upload_api_checks_size_content_and_foreign_replacement(self):
        row = self.create()
        other = self.create(key="other-upload")
        path = self.url + str(row.pk) + "/evidence/"
        with (
            TemporaryDirectory() as directory,
            override_settings(
                DOCUMENTS_EXIT_INSTITUTIONS=[self.institution.pk],
                DOCUMENTS_STORAGE_ROOT=Path(directory),
            ),
        ):

            def payload():
                return {
                    "title": "Report",
                    "category": "BUDGET",
                    "version": s.version(row.pk),
                    "file": SimpleUploadedFile(
                        "report.pdf", pdf(), content_type="application/pdf"
                    ),
                }

            with override_settings(DOCUMENTS_MAX_BYTES=5):
                response = self.client.post(path, payload(), format="multipart")
                self.assertEqual(response.status_code, 400, response.data)
            response = self.client.post(path, payload(), format="multipart")
            self.assertEqual(response.status_code, 201, response.data)
            values = payload()
            values["replaces"] = response.data["id"]
            values["version"] = s.version(other.pk)
            response = self.client.post(
                self.url + str(other.pk) + "/evidence/", values, format="multipart"
            )
            self.assertEqual(response.status_code, 404, response.data)
            self.assertEqual(ActivityAttachment.objects.count(), 1)

    def test_funding_consistency_and_controlled_status_history(self):
        second = refs.FundingType.objects.create(
            pk=2, funding_type_code="OTHER", funding_type_name="Other"
        )
        with self.assertRaises(ValidationError):
            self.create(funding_type_id=second.pk)
        row = self.create()
        first = ResearchProposalStatusHistory.objects.get(proposal=row)
        with self.assertRaises(ValidationError):
            first.delete()
        with self.assertRaises(ValidationError):
            ResearchProposalStatusHistory.objects.filter(pk=first.pk).update(
                remarks="tamper"
            )
        response = self.client.get(self.url + str(row.pk) + "/timeline/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["results"][0]["to_status"], "DRAFT")
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {"research_status_id": 999},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
            )

    def test_inactive_pi_and_external_funder_requirement(self):
        self.employee.employment_status = "DRAFT"
        self.employee.save()
        with self.assertRaises(ValidationError):
            self.create()
        self.employee.employment_status = "ACTIVE"
        self.employee.save()
        row = self.create(funding_agency_id=None)
        with self.assertRaises(ValidationError):
            s.workflow(
                self.root, row.pk, "submit", "", s.version(row.pk), "missing-funder"
            )
        self.assertEqual(
            ResearchProposalStatusHistory.objects.filter(proposal=row).count(), 1
        )

    def test_native_history_guard_and_lookup_labels(self):
        from django.db import DatabaseError

        row = self.create()
        history = ResearchProposalStatusHistory.objects.get(proposal=row)
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE platform_research_proposal_status_history SET remarks='tamper' WHERE id=%s",
                [history.pk],
            )
        history.refresh_from_db()
        self.assertEqual(history.remarks, "Draft created")
        detail = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(
            detail.data["department_name"], self.department.department_name
        )
        for resource in ("funding_agencies", "funding_types", "statuses", "domains"):
            self.assertEqual(
                self.client.get(
                    "/api/v1/research-proposals/lookups/" + resource + "/"
                ).status_code,
                200,
            )

    @override_settings(RESEARCH_PROPOSALS_EVENT_HANDLER="synthetic.adapter")
    def test_events_run_after_commit_without_rolling_back_proposal(self):
        with patch("apps.research_proposals.events.import_string") as load:
            load.return_value.side_effect = RuntimeError("private delivery detail")
            with (
                self.assertLogs(
                    "apps.research_proposals.events", level="ERROR"
                ) as captured,
                self.captureOnCommitCallbacks(execute=True),
            ):
                row = self.create()
                load.assert_not_called()
            self.assertTrue(ResearchProposal.objects.filter(pk=row.pk).exists())
            self.assertEqual(load.call_count, 1)
            self.assertNotIn("private delivery detail", str(captured.output))

    @override_settings(RESEARCH_PROPOSALS_EVENT_HANDLER="synthetic.adapter")
    def test_rolled_back_creation_never_emits_event(self):

        with (
            patch("apps.research_proposals.events.import_string") as load,
            self.captureOnCommitCallbacks(execute=True),
            patch(
                "apps.research_proposals.services.record",
                side_effect=RuntimeError("rollback"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        load.assert_not_called()
        self.assertEqual(ResearchProposalStatusHistory.objects.count(), 0)

    def test_report_money_is_exact_and_float_input_is_rejected(self):
        self.create(requested_amount=Decimal("99999999999999.99"))
        response = self.client.get(self.url + "summary/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.json()["amounts_by_currency"][0]["amount"], "99999999999999.99"
        )
        self.assertEqual(
            response.json()["groups"]["department"][0]["requested_total"],
            "99999999999999.99",
        )
        response = self.client.post(
            self.url,
            {
                "context": self.context,
                "activity": self.values | {"requested_amount": 1.25},
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="floating-money",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_shared_specialization_guard_rejects_conflicting_child(self):
        from apps.faculty_internships.models import FacultyInternship

        row = self.create()
        FacultyInternship.objects.create(
            staff_activity_id=row.pk,
            organization=self.organization,
            internship_title="Conflicting imported child",
        )
        with self.assertRaises(ValidationError):
            s.update_proposal(
                self.root,
                row.pk,
                {"proposal_title": "Should not save"},
                expected_version=s.version(row.pk),
            )
        row.refresh_from_db()
        self.assertEqual(row.proposal_title, self.values["proposal_title"])
