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
from apps.faculty_internships import services as s
from apps.faculty_internships.models import FacultyInternship
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink, Employee, EmployeeAssignment
from apps.people_master.tests.test_services import fixture
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_profile import models as refs


@override_settings(
    FACULTY_INTERNSHIPS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class InternshipTests(TestCase):
    def setUp(self):
        fixture(self)
        self.employee = Employee.objects.create(
            institution=self.institution,
            employment_source=self.source,
            employee_number="M24-SYNTHETIC",
            first_name="Synthetic",
            display_name="Synthetic",
            joining_date=date(2020, 1, 1),
            employment_type="REGULAR",
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
        call_command("seed_faculty_internships", stdout=StringIO())
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
        self.sector = refs.IndustrySector.objects.create(
            sector_code="TEST", sector_name="Test sector"
        )
        self.role = iam.Role.objects.create(
            role_code="M24_TEST",
            role_name="M24 test",
            role_category="SYSTEM",
            role_level="GLOBAL",
        )
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="FACULTY_INTERNSHIPS."
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
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }
        self.values = {
            "organization_id": self.organization.pk,
            "industry_sector_id": self.sector.pk,
            "internship_title": "Synthetic internship",
        }
        self.client = APIClient()
        self.client.force_authenticate(self.root)
        self.url = "/api/v1/faculty-internships/activities/"

    def create(self, key="create-1", **values):
        return s.save_activity(
            self.root, self.values | values, context=self.context, key=key
        )

    def reviewer(self):
        user = get_user_model().objects.create_user(username="m24reviewer")
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
        self.assertEqual(FacultyInternship.objects.count(), 1)
        self.assertEqual(
            row.staff_activity.activity_type.activity_type_code, s.TYPE_CODE
        )
        with self.assertRaises(s.Conflict):
            self.create(internship_title="changed")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)

    def test_validation_and_rollback(self):
        for values in [
            {"internship_title": " "},
            {"mentor_email": "invalid"},
            {"currency_code": "R1"},
            {"stipend_incentive_amount": Decimal(-1)},
            {"stipend_incentive_type": "WRONG"},
            {"staff_activity_id": 999},
            {"organization_id": 999},
        ]:
            before = StaffActivity.objects.count()
            with self.assertRaises((ValidationError, NotFound)):
                self.create(**values)
            self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(ActivityCommandReceipt.objects.count(), 0)
        row = self.create(stipend_incentive_amount=Decimal(25), currency_code="usd")
        self.assertIsNone(row.stipend_incentive_amount)
        self.assertEqual(row.currency_code, "USD")

    def test_invalid_dates_assignment_and_inactive_master(self):
        self.context["end_date"] = "2019-01-01"
        with self.assertRaises(ValidationError):
            self.create()
        self.context["end_date"] = "2026-01-31"
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
            {"internship_title": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"internship_title": "stale"},
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
                {"internship_title": "No"},
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
            {"internship_title": "Corrected"},
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
        self.assertTrue(FacultyInternship.objects.filter(pk=pk).exists())

    def test_scope_deny_self_and_export(self):
        row = self.create(internship_title="=HYPERLINK(1)")
        response = self.client.get(self.url + "export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=HYPERLINK", response.content.decode())
        self.grant.scope_type = "DEPARTMENT"
        from apps.organization.models import Department

        self.grant.department = Department.objects.create(
            campus=self.campus, department_code="OTHER24", department_name="Other"
        )
        self.grant.save()
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
            permission_code="FACULTY_INTERNSHIPS.ACTIVITY.READ"
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
        self.create(
            stipend_incentive_type="STIPEND", stipend_incentive_amount=Decimal(20)
        )
        with CaptureQueriesContext(connection) as first:
            self.client.get(self.url)
        for i in range(4):
            self.create(
                key=f"create-{i + 2}",
                stipend_incentive_type="INCENTIVE",
                stipend_incentive_amount=Decimal(3),
                currency_code="USD",
            )
        with CaptureQueriesContext(connection) as later:
            self.client.get(self.url)
        self.assertEqual(len(first), len(later))
        self.assertEqual(
            self.client.get(self.url, {"stipend_type": "STIPEND"}).data["count"], 1
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
                "/api/v1/faculty-internships/lookups/assignments/"
            ).status_code,
            200,
        )

    def test_native_schema_and_database_constraint(self):
        row = self.create()
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE faculty_internship")
            ddl = cursor.fetchone()[1].lower()
            for fragment in [
                "bigint unsigned",
                "decimal(14,2)",
                "char(3)",
                "chk_faculty_internship_amount",
                "fk_faculty_internship_activity",
                "utf8mb4_unicode_ci",
            ]:
                self.assertIn(fragment, ddl)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FacultyInternship.objects.filter(pk=row.pk).update(
                stipend_incentive_amount=-1
            )

    def test_configuration_idempotency_missing_and_disabled(self):
        count = iam.UserRoleAssignment.objects.count()
        call_command("seed_faculty_internships", stdout=StringIO())
        call_command("seed_faculty_internships", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        refs.ApprovalStatus.objects.filter(status_code="DRAFT").update(is_active=False)
        with self.assertRaises(ValidationError):
            self.create()
        with override_settings(FACULTY_INTERNSHIPS_ENABLED=False):
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
                    category="COMPLETION_CERTIFICATE",
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
                    "apps.faculty_internships.services.ActivityAttachment.objects.create",
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
            {"internship_title": "Changed"},
            activity_id=row.pk,
            expected_version=original,
        )
        s.save_activity(
            self.root,
            {"internship_title": self.values["internship_title"]},
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
                "apps.faculty_internships.services.record",
                side_effect=RuntimeError("synthetic"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(FacultyInternship.objects.count(), 0)
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
                    "activity": {"internship_title": "stale"},
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
                    "category": "WORK_REPORT",
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
