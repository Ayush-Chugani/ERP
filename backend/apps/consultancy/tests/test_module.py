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

from apps.consultancy import services as s
from apps.consultancy.models import (
    ConsultancyProject,
    ProjectMilestone,
    ProjectReceipt,
    ReceiptVoid,
)
from apps.documents_exit.models import FileObject
from apps.documents_exit.tests.providers import pdf
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink, Employee
from apps.research_proposals.tests import test_module as baseline
from apps.staff_activities.models import ActivityAttachment, StaffActivity


@override_settings(
    CONSULTANCY_ENABLED=True,
    RESEARCH_PROPOSALS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConsultancyTests(TestCase):
    def setUp(self):
        baseline.ProposalTests.setUp(self)
        call_command("seed_consultancy", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="CONSULTANCY."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.values = {
            "consultancy_title": "Synthetic consultancy",
            "client_organization_id": self.organization.pk,
            "project_start_date": "2026-01-02",
            "consultancy_amount": "100.00",
            "faculty_incentive_share": "200.00",
        }
        self.url = "/api/v1/consultancy/activities/"

    def create(self, key="create", **values):
        return s.save_activity(
            self.root, self.values | values, context=self.context, key=key
        )

    def receipt(self, row, key="receipt", **values):
        return s.extension(
            self.root,
            row.pk,
            "receipts",
            {
                "receipt_date": "2026-02-01",
                "amount": "125.01",
                "currency_code": "INR",
                "reference_number": key,
            }
            | values,
            expected_version=s.version(row.pk),
            reason="Received",
            key=key,
        )

    def revoke(self, resource, action):
        iam.RolePermission.objects.filter(
            role=self.role,
            permission__permission_code=f"CONSULTANCY.{resource}.{action}",
        ).delete()

    def member(self):
        row = Employee.objects.get(pk=self.employee.pk)
        row.pk = None
        row.employee_number = "CO-27"
        row.display_name = "Co-consultant"
        row.save()
        return row

    def test_atomic_creation_retry_and_rollback(self):
        row = self.create()
        self.assertEqual(row.pk, self.create().pk)
        self.assertEqual(row.status, "PROPOSED")
        self.assertEqual(row.staff_activity.activity_type.activity_group, "CONSULTANCY")
        with self.assertRaises(s.Conflict):
            self.create(consultancy_title="Changed")
        with (
            patch(
                "apps.consultancy.services.record", side_effect=RuntimeError("audit")
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create(key="fail")
        self.assertEqual(ConsultancyProject.objects.count(), 1)
        self.assertEqual(StaffActivity.objects.count(), 1)
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()

    def test_validation_matrix(self):
        for values in [
            {"consultancy_title": " "},
            {"consultancy_type": "INVALID"},
            {"status": "APPROVED"},
            {"amount_received": "5"},
            {"principal_consultant_employee_id": 5},
            {"consultancy_amount": "-1"},
            {"consultancy_amount": 1.1},
            {"faculty_incentive_share": "-1"},
            {"consultancy_amount": "0.001"},
            {"currency_code": "I1R"},
            {"completion_date": "2025-01-01"},
            {"work_order_number": "X" * 151},
        ]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.create(**values)
            self.assertFalse(StaffActivity.objects.exists())
        self.organization.is_active = False
        self.organization.save()
        with self.assertRaises(ValidationError):
            self.create()

    def test_receipts_overcollection_incentive_and_zero_metrics(self):
        row = self.create()
        self.receipt(row)
        row.refresh_from_db()
        self.assertEqual(row.amount_received, Decimal("125.01"))
        self.assertEqual(row.faculty_incentive_share, Decimal(200))
        self.assertEqual(
            s.metrics(row),
            {"balance_receivable": "-25.01", "collection_percentage": "125.01"},
        )
        zero = self.create(
            key="zero", consultancy_amount="0", faculty_incentive_share=None
        )
        self.assertIsNone(s.metrics(zero)["collection_percentage"])
        self.receipt(zero, key="large", amount="99999999999999.99")
        zero.refresh_from_db()
        self.assertEqual(str(zero.amount_received), "99999999999999.99")
        with self.assertRaises(ValidationError):
            self.receipt(zero, key="overflow", amount="0.01")

    def test_receipt_currency_reference_and_immutable_corrections(self):
        row = self.create()
        self.receipt(row)
        for values in [
            {"currency_code": "USD"},
            {"amount": "-1"},
            {"amount": "1.234"},
            {"amount": 1.2},
            {"receipt_date": "invalid"},
            {"reference_number": "receipt"},
        ]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.receipt(row, key="bad", **values)
        entry = ProjectReceipt.objects.get(project=row)
        with self.assertRaises(ValidationError):
            s.extension(
                self.root,
                row.pk,
                "receipts",
                {"amount": "2.00"},
                item_id=entry.pk,
                expected_version=s.version(row.pk),
                reason="Change",
                key="edit",
            )
        s.extension(
            self.root,
            row.pk,
            "receipts",
            {},
            item_id=entry.pk,
            void=True,
            expected_version=s.version(row.pk),
            reason="Correction",
            key="void",
        )
        row.refresh_from_db()
        self.assertEqual(row.amount_received, 0)
        self.assertEqual(ProjectReceipt.objects.count(), 1)
        self.assertEqual(ReceiptVoid.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.receipt(row, key="new", reference_number="receipt")

    def test_workflow_without_payment_gate_and_version_conflict(self):
        row = self.create()
        old = s.version(row.pk)
        s.workflow(self.root, row.pk, "approve", "Approved", old, "approve")
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"consultancy_title": "Other"},
                activity_id=row.pk,
                expected_version=old,
                reason="Change",
            )
        s.workflow(self.root, row.pk, "start", "Started", s.version(row.pk), "start")
        with self.assertRaises(ValidationError):
            s.workflow(
                self.root, row.pk, "complete", "Done", s.version(row.pk), "complete"
            )
        s.save_activity(
            self.root,
            {"completion_date": "2026-03-01"},
            activity_id=row.pk,
            expected_version=s.version(row.pk),
            reason="Completion report",
        )
        s.workflow(self.root, row.pk, "complete", "Done", s.version(row.pk), "complete")
        s.workflow(
            self.root,
            row.pk,
            "close",
            "Administrative closure",
            s.version(row.pk),
            "close",
        )
        row.refresh_from_db()
        self.assertEqual(row.status, "CLOSED")
        self.assertEqual(row.amount_received, 0)
        self.receipt(row)
        s.archive(self.root, row.pk, s.version(row.pk))
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)

    def test_team_membership_and_milestone_dates(self):
        row = self.create()
        employee = self.member()
        team = {
            "employee_id": employee.pk,
            "project_role": "Co-consultant",
            "start_date": "2026-01-02",
        }
        s.extension(
            self.root,
            row.pk,
            "team",
            team,
            expected_version=s.version(row.pk),
            reason="Assigned",
            key="team",
        )
        with self.assertRaises(ValidationError):
            s.extension(
                self.root,
                row.pk,
                "team",
                team,
                expected_version=s.version(row.pk),
                reason="Duplicate",
                key="duplicate",
            )
        with self.assertRaises(ValidationError):
            s.extension(
                self.root,
                row.pk,
                "team",
                team | {"employee_id": self.employee.pk},
                expected_version=s.version(row.pk),
                reason="Principal",
                key="principal",
            )
        milestone = {"sequence": 1, "title": "Delivery", "due_date": "2026-03-01"}
        s.extension(
            self.root,
            row.pk,
            "milestones",
            milestone,
            expected_version=s.version(row.pk),
            reason="Planned",
            key="milestone",
        )
        item = ProjectMilestone.objects.get(project=row)
        with self.assertRaises(ValidationError):
            s.extension(
                self.root,
                row.pk,
                "milestones",
                {"status": "ACCEPTED"},
                item_id=item.pk,
                expected_version=s.version(row.pk),
                reason="Accept",
                key="accept",
            )
        s.extension(
            self.root,
            row.pk,
            "milestones",
            {
                "status": "ACCEPTED",
                "completion_date": "2026-03-01",
                "acceptance_date": "2026-03-02",
            },
            item_id=item.pk,
            expected_version=s.version(row.pk),
            reason="Accepted",
            key="accept-ok",
        )
        progress = self.client.get(
            self.url + str(row.pk) + "/extensions/milestones/"
        ).data["progress"]
        self.assertEqual(
            progress, {"total": 1, "completed": 1, "overdue": 0, "percentage": "100.00"}
        )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {"completion_date": "2026-02-01"},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
                reason="Bad boundary",
            )

    def test_every_mutation_requires_its_own_permission(self):
        row = self.create()
        self.receipt(row)
        entry = ProjectReceipt.objects.get(project=row)
        for resource, action in [
            ("ACTIVITY", "UPDATE"),
            ("STATUS", "UPDATE"),
            ("FINANCE", "UPDATE"),
            ("FINANCE", "DELETE"),
            ("TEAM", "UPDATE"),
            ("MILESTONE", "UPDATE"),
            ("ACTIVITY", "DELETE"),
        ]:
            with self.subTest(resource=resource, action=action):
                perm = iam.Permission.objects.get(
                    permission_code=f"CONSULTANCY.{resource}.{action}"
                )
                self.revoke(resource, action)
                with self.assertRaises(PermissionDenied):
                    if resource == "ACTIVITY" and action == "UPDATE":
                        s.save_activity(
                            self.root,
                            {},
                            activity_id=row.pk,
                            expected_version=s.version(row.pk),
                            reason="Edit",
                        )
                    elif resource == "ACTIVITY":
                        s.archive(self.root, row.pk, s.version(row.pk))
                    elif resource == "STATUS":
                        s.workflow(
                            self.root,
                            row.pk,
                            "approve",
                            "Approve",
                            s.version(row.pk),
                            "status-denied",
                        )
                    elif resource == "FINANCE" and action == "UPDATE":
                        self.receipt(row, key="denied")
                    elif resource == "FINANCE":
                        s.extension(
                            self.root,
                            row.pk,
                            "receipts",
                            {},
                            item_id=entry.pk,
                            void=True,
                            expected_version=s.version(row.pk),
                            reason="Void",
                            key="denied-void",
                        )
                    else:
                        s.extension(
                            self.root,
                            row.pk,
                            "team" if resource == "TEAM" else "milestones",
                            {},
                            expected_version=s.version(row.pk),
                            reason="Change",
                            key="denied-" + resource,
                        )
                iam.RolePermission.objects.create(role=self.role, permission=perm)

    def test_api_redaction_mass_assignment_and_cross_project_receipt(self):
        result = self.client.post(
            self.url,
            {"activity": self.values, "context": self.context},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api",
        )
        self.assertEqual(result.status_code, 201, result.data)
        pk = result.data["staff_activity"]
        row = ConsultancyProject.objects.get(pk=pk)
        self.receipt(row)
        other = self.create(key="other")
        entry = ProjectReceipt.objects.get(project=row)
        bad = self.client.post(
            self.url + str(other.pk) + "/extensions/receipts/",
            {
                "item_id": entry.pk,
                "void": True,
                "version": s.version(other.pk),
                "reason": "Cross project",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="cross",
        )
        self.assertEqual(bad.status_code, 404)
        self.revoke("FINANCE", "READ")
        for path in [self.url, self.url + pk + "/"]:
            data = self.client.get(path).data
            data = data["results"][0] if "results" in data else data
            self.assertNotIn("consultancy_amount", data)
            self.assertNotIn("amount_received", data)
        self.assertEqual(
            self.client.get(self.url + pk + "/extensions/receipts/").status_code, 403
        )
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)

    def test_native_constraints_and_append_only_receipts(self):
        row = self.create()
        self.receipt(row)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConsultancyProject.objects.filter(pk=row.pk).update(consultancy_amount=-1)
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "DELETE FROM platform_consultancy_receipt WHERE project_id=%s", [row.pk]
            )
        self.assertEqual(ProjectReceipt.objects.count(), 1)

    def test_filters_reports_constant_queries_and_exact_totals(self):
        self.create(
            consultancy_title="=HYPERLINK(1)", consultancy_amount="99999999999999.99"
        )
        with CaptureQueriesContext(connection) as first:
            self.client.get(self.url)
        for i in range(3):
            self.create(key=str(i), currency_code="USD")
        with CaptureQueriesContext(connection) as many:
            self.client.get(self.url)
        self.assertEqual(len(first), len(many))
        data = self.client.get(self.url + "summary/").data
        self.assertEqual(data["count"], 4)
        self.assertIn("99999999999999.99", str(data))
        self.assertIn(
            "'=HYPERLINK", self.client.get(self.url + "export/").content.decode()
        )
        self.assertEqual(
            self.client.get(self.url + "?ordering=password").status_code, 400
        )
        self.assertEqual(self.client.get(self.url + "?status=INVALID").status_code, 400)
        self.assertEqual(
            self.client.get(self.url + "?search=Synthetic%20consultancy").data["count"],
            3,
        )

    def test_api_extension_writes_and_retained_audit(self):
        row = self.create()
        path = self.url + str(row.pk) + "/extensions/receipts/"
        payload = {
            "values": {
                "receipt_date": "2026-02-01",
                "amount": "12.34",
                "currency_code": "INR",
                "reference_number": "API",
            },
            "version": s.version(row.pk),
            "reason": "Receipt",
        }
        result = self.client.post(
            path,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="receipt-api",
            HTTP_X_REQUEST_ID="test-correlation",
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["amount_received"], "12.34")
        self.assertEqual(
            self.client.post(
                path, payload, format="json", HTTP_IDEMPOTENCY_KEY="receipt-api"
            ).status_code,
            200,
        )
        audit = self.client.get(self.url + str(row.pk) + "/financial-history/").data[
            "results"
        ][0]
        self.assertEqual(audit["request_identifier"], "test-correlation")

    def test_flags_and_seed_idempotency(self):
        count = iam.UserRoleAssignment.objects.count()
        call_command("seed_consultancy", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        self.assertEqual(
            iam.Permission.objects.filter(
                permission_code__startswith="CONSULTANCY."
            ).count(),
            16,
        )
        with override_settings(CONSULTANCY_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_scope_deny_self_and_export(self):
        row = self.create(consultancy_title="=HYPERLINK(1)")
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
        self.assertEqual(ConsultancyProject.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)
        self.grant.scope_type = "SELF"
        self.grant.department = None
        self.grant.save()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        AccountLink.objects.create(user=self.root, employee=self.employee)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        perm = iam.Permission.objects.get(permission_code="CONSULTANCY.ACTIVITY.READ")
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
                    category="WORK_ORDER",
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
                    "apps.consultancy.services.ActivityAttachment.objects.create",
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

    def test_unicode_text_limits_nullable_fields_and_nonunique_core_references(self):
        self.create(
            consultancy_title=chr(0x0938) + chr(0x5408),
            work_order_number="SHARED",
            faculty_incentive_share=None,
            deliverables="Unicode deliverables",
        )
        self.create(key="second-reference", work_order_number="SHARED")
        with self.assertRaises(ValidationError):
            self.create(key="text-overflow", deliverables=chr(0x1F600) * 16384)
        self.assertEqual(ConsultancyProject.objects.count(), 2)

    def test_document_permission_is_independent_from_metadata_edit(self):
        row = self.create()
        self.revoke("DOCUMENT", "UPDATE")
        with (
            override_settings(
                DOCUMENTS_EXIT_ENABLED=True,
                DOCUMENTS_EXIT_INSTITUTIONS=[self.institution.pk],
            ),
            self.assertRaises(PermissionDenied),
        ):
            s.upload_attachment(
                actor=self.root,
                pk=row.pk,
                expected_version=s.version(row.pk),
                upload=SimpleUploadedFile(
                    "evidence.pdf", pdf(), content_type="application/pdf"
                ),
                title="Work order",
                category="WORK_ORDER",
            )

    def test_populated_reversal_is_refused_without_deleting_data(self):
        from importlib import import_module

        self.create()
        migration = import_module("apps.consultancy.migrations.0003_retention")
        from django.apps import apps

        with self.assertRaises(RuntimeError):
            migration.reverse(apps, connection.schema_editor())
        self.assertEqual(ConsultancyProject.objects.count(), 1)

    def test_advance_receipts_are_allowed_without_invented_date_policy(self):
        row = self.create()
        self.receipt(row, receipt_date="2025-12-01")
        row.refresh_from_db()
        self.assertEqual(row.amount_received, Decimal("125.01"))
