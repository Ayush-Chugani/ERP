from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, transaction
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

from apps.awards import services as s
from apps.awards.models import (
    AwardStatusHistory,
    StaffAward,
)
from apps.documents_exit.models import FileObject
from apps.documents_exit.tests.providers import pdf
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink
from apps.research_proposals.tests import test_module as base_fixture
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_profile import models as refs


@override_settings(
    AWARDS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class AwardTests(TestCase):
    def setUp(self):
        base_fixture.ProposalTests.setUp(self)
        call_command("seed_awards", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="AWARDS."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.category = refs.AwardCategory.objects.create(
            category_code="TEST", category_name="Synthetic category"
        )
        self.values = {
            "award_name": "Synthetic award",
            "award_category_id": self.category.pk,
            "award_date": date(2026, 1, 1),
        }
        self.url = "/api/v1/awards/activities/"

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
        self.assertEqual(StaffAward.objects.count(), 1)
        self.assertEqual(
            row.staff_activity.activity_type.activity_type_code, s.TYPE_CODE
        )
        with self.assertRaises(s.Conflict):
            self.create(award_name="changed")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)

    def test_update_version_and_protected_context(self):
        row = self.create()
        token = s.version(row.pk)
        s.save_activity(
            self.root,
            {"award_name": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"award_name": "stale"},
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
                {"award_name": "No"},
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
            {"award_name": "Corrected"},
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
        self.assertTrue(StaffAward.objects.filter(pk=pk).exists())

    def test_scope_deny_self_and_export(self):
        row = self.create(award_name="=HYPERLINK(1)")
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
        self.assertEqual(StaffAward.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)
        self.grant.scope_type = "SELF"
        self.grant.department = None
        self.grant.save()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        AccountLink.objects.create(user=self.root, employee=self.employee)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        perm = iam.Permission.objects.get(permission_code="AWARDS.ACTIVITY.READ")
        iam.UserPermissionOverride.objects.create(
            user=self.root,
            permission=perm,
            permission_effect="DENY",
            justification="Synthetic deny test",
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    def test_configuration_idempotency_missing_and_disabled(self):
        count = iam.UserRoleAssignment.objects.count()
        call_command("seed_awards", stdout=StringIO())
        call_command("seed_awards", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        refs.ApprovalStatus.objects.filter(status_code="DRAFT").update(is_active=False)
        with self.assertRaises(ValidationError):
            self.create()
        with override_settings(AWARDS_ENABLED=False):
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
                    category="CERTIFICATE",
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
                    "apps.awards.services.ActivityAttachment.objects.create",
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
            {"award_name": "Changed"},
            activity_id=row.pk,
            expected_version=original,
        )
        s.save_activity(
            self.root,
            {"award_name": self.values["award_name"]},
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
                "apps.awards.services.record",
                side_effect=RuntimeError("synthetic"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(StaffAward.objects.count(), 0)
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
                    "activity": {"award_name": "stale"},
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
                    "category": "APPROVED_EVIDENCE",
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

    def test_shared_specialization_guard_rejects_conflicting_child(self):
        from apps.faculty_internships.models import FacultyInternship

        row = self.create()
        FacultyInternship.objects.create(
            staff_activity_id=row.pk,
            organization=self.organization,
            internship_title="Conflicting imported child",
        )
        with self.assertRaises(ValidationError):
            s.update_activity(
                self.root,
                row.pk,
                {"award_name": "Should not save"},
                expected_version=s.version(row.pk),
            )
        row.refresh_from_db()
        self.assertEqual(row.award_name, self.values["award_name"])

    def test_lookup_and_master_permissions(self):
        self.create()
        path = "/api/v1/awards/lookups/"
        for resource in (
            "categories",
            "organizations",
            "statuses",
            "years",
            "assignments",
        ):
            self.assertEqual(self.client.get(path + resource + "/").status_code, 200)
        admin = "/api/v1/awards/category-admin/"
        response = self.client.post(
            admin,
            {"category_code": "NEW", "category_name": "New category"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="AWARDS.MASTER.UPDATE"
        ).delete()
        self.assertEqual(self.client.get(admin).status_code, 403)
        self.assertEqual(
            self.client.post(
                admin, {"category_code": "NO", "category_name": "Denied"}, format="json"
            ).status_code,
            403,
        )

    def test_filters_reports_and_constant_queries(self):
        self.create()
        with CaptureQueriesContext(connection) as first:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
        for i in range(4):
            self.create(key=f"more-{i}", award_reference_number="Other")
        with CaptureQueriesContext(connection) as later:
            self.client.get(self.url)
        self.assertEqual(len(first), len(later))
        self.assertEqual(
            self.client.get(self.url, {"search": "Other"}).data["count"], 4
        )
        self.assertEqual(
            self.client.get(self.url, {"date_from": "invalid"}).status_code, 400
        )
        self.assertEqual(
            self.client.get(self.url, {"ordering": "password"}).status_code, 400
        )
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 5)
        iam.RolePermission.objects.filter(
            role=self.role,
            permission__permission_code="AWARDS.ACTIVITY.EXPORT",
        ).delete()
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url).data["count"], 5)

    def test_native_schema_history_and_rollback_guard(self):
        from importlib import import_module

        from django.apps import apps
        from django.db import DatabaseError

        row = self.create()
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE staff_award")
            ddl = cursor.fetchone()[1].lower()
            for fragment in [
                "bigint unsigned",
                "smallint unsigned",
                "fk_staff_award_category",
                "decimal(14,2)",
                "chk_staff_award_amounts",
                "char(3)",
                "varchar(500)",
                "utf8mb4_unicode_ci",
            ]:
                self.assertIn(fragment, ddl)
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("UPDATE platform_awards_status_history SET remarks='tamper'")
        with (
            self.assertRaises(RuntimeError),
            connection.schema_editor(atomic=False) as editor,
        ):
            import_module("apps.awards.migrations.0002_retain_status_history").reverse(
                apps, editor
            )
        self.assertEqual(
            AwardStatusHistory.objects.get(activity=row).remarks,
            "Draft created",
        )

    @override_settings(AWARDS_EVENT_HANDLER="synthetic.adapter")
    def test_events_commit_retry_and_rollback(self):
        row = self.create()
        token = s.version(row.pk)
        with (
            patch("apps.awards.events.import_string") as load,
            self.captureOnCommitCallbacks(execute=True),
        ):
            s.workflow(self.root, row.pk, "submit", "", token, "notify")
            s.workflow(self.root, row.pk, "submit", "", token, "notify")
            load.assert_not_called()
        self.assertEqual(load.return_value.call_count, 1)
        self.assertEqual(
            load.return_value.call_args.kwargs["event"]["status"], "SUBMITTED"
        )
        reviewer = self.reviewer()
        with (
            patch("apps.awards.events.import_string") as load,
            self.captureOnCommitCallbacks(execute=True),
        ):
            try:
                with transaction.atomic():
                    s.workflow(
                        reviewer,
                        row.pk,
                        "return",
                        "Fix",
                        s.version(row.pk),
                        "rollback-event",
                    )
                    raise RuntimeError("rollback")
            except RuntimeError:
                pass
        load.assert_not_called()
        self.assertEqual(AwardStatusHistory.objects.filter(activity=row).count(), 2)

    def test_money_validation_normalization_and_required_fields_atomic(self):
        invalid = [
            {"award_name": " "},
            {"award_date": None},
            {"award_date": date(2026, 1, 2)},
            {"award_name": "x" * 501},
            {"award_reference_number": "x" * 151},
            {"currency_code": ""},
            {"currency_code": "US"},
            {"currency_code": "1NR"},
            {"citation_details": chr(0x1F600) * 16384},
            {"award_category_id": 999999},
            {"staff_activity_id": 1},
        ]
        for field in ("cash_prize_amount", "incentive_amount"):
            invalid += [
                {field: v}
                for v in (
                    "-0.01",
                    "1000000000000.00",
                    "1.001",
                    "NaN",
                    "Infinity",
                    0.1,
                    True,
                )
            ]
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises((ValidationError, NotFound)):
                    self.create(**values)
                self.assertEqual(StaffActivity.objects.count(), 0)
        row = self.create(
            award_category_id=None,
            awarding_organization_id=None,
            cash_prize_amount="0.00",
            incentive_amount="999999999999.99",
            currency_code=" usd ",
        )
        row.refresh_from_db()
        self.assertEqual(str(row.cash_prize_amount), "0.00")
        self.assertEqual(str(row.incentive_amount), "999999999999.99")
        self.assertEqual(row.currency_code, "USD")
        self.assertIsNone(row.award_category_id)

    def test_api_money_strings_put_patch_and_derived_context(self):
        self.context.pop("context_date")
        response = self.client.post(
            self.url,
            {
                "context": self.context,
                "activity": self.values
                | {
                    "cash_prize_amount": "999999999999.99",
                    "incentive_amount": "0.00",
                    "currency_code": "usd",
                },
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="money",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["cash_prize_amount"], "999999999999.99")
        self.assertEqual(response.data["incentive_amount"], "0.00")
        self.assertEqual(response.data["currency_code"], "USD")
        url = self.url + response.data["staff_activity"] + "/"
        for field in ("cash_prize_amount", "incentive_amount"):
            bad = self.client.patch(
                url,
                {"version": response.data["version"], "activity": {field: 1.1}},
                format="json",
            )
            self.assertEqual(bad.status_code, 400, bad.data)
        response = self.client.patch(
            url,
            {
                "version": response.data["version"],
                "activity": {"award_name": "Updated"},
            },
            format="json",
        )
        self.assertEqual(response.data["incentive_amount"], "0.00")
        response = self.client.put(
            url,
            {
                "version": response.data["version"],
                "activity": {"award_name": "Replaced", "award_date": "2026-01-01"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["incentive_amount"])
        self.assertIsNone(response.data["award_category"])
        self.assertEqual(response.data["currency_code"], "INR")
        bad = self.client.put(
            url,
            {
                "version": response.data["version"],
                "activity": {"award_name": "No date"},
            },
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

    def test_native_negative_constraint_unique_child_and_nulls(self):
        from django.db import IntegrityError

        row = self.create()
        for field in ("cash_prize_amount", "incentive_amount"):
            with self.assertRaises(IntegrityError), transaction.atomic():
                StaffAward.objects.filter(pk=row.pk).update(**{field: "-0.01"})
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffAward.objects.create(
                staff_activity_id=row.pk,
                award_name="Duplicate",
                award_date=date(2026, 1, 1),
            )
        self.assertIsNone(StaffAward.objects.get(pk=row.pk).cash_prize_amount)

    def test_currency_totals_filters_and_scoped_exports(self):
        self.create(
            cash_prize_amount="999999999999.99",
            incentive_amount="0.00",
            award_reference_number="REF-ONE",
            awarding_organization_id=self.organization.pk,
        )
        self.create(key="two", cash_prize_amount="999999999999.99")
        self.create(
            key="usd",
            currency_code="USD",
            cash_prize_amount="0.01",
            incentive_amount="5.00",
        )
        self.create(key="none", currency_code="EUR", award_category_id=None)
        report = self.client.get(self.url + "summary/")
        totals = {r["currency_code"]: r for r in report.data["totals_by_currency"]}
        self.assertEqual(totals["INR"]["cash_prize_amount"], "1999999999999.98")
        self.assertEqual(totals["USD"]["cash_prize_amount"], "0.01")
        self.assertIsNone(totals["EUR"]["cash_prize_amount"])
        for query, count in [
            ({"currency": "usd"}, 1),
            ({"cash_prize_present": "true"}, 3),
            ({"incentive_present": "false"}, 2),
            ({"cash_prize_min": "1"}, 2),
            ({"cash_prize_max": "0.01"}, 1),
            ({"incentive_min": "0", "incentive_max": "0"}, 1),
            ({"search": "REF-ONE"}, 1),
            ({"category": self.category.pk}, 3),
            ({"awarding_organization": self.organization.pk}, 1),
            ({"date_from": "2026-01-01", "date_to": "2026-01-01"}, 4),
        ]:
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.url, query).data["count"], count)
        self.assertEqual(
            self.client.get(self.url, {"cash_prize_min": "-1"}).status_code, 400
        )
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="AWARDS.ACTIVITY.EXPORT"
        ).delete()
        self.assertEqual(
            self.client.get(self.url + "summary/").data["totals_by_currency"], []
        )
        self.assertEqual(
            len(self.client.get(self.url + "export/").content.decode().splitlines()), 1
        )

    def test_optional_active_references_unicode_boundaries_and_category_retention(self):
        from django.db.models.deletion import ProtectedError

        row = self.create(
            award_name=chr(0x1F600) * 500,
            award_reference_number="R" * 150,
            awarding_organization_id=self.organization.pk,
            citation_details="Line one\nLine two",
        )
        row.refresh_from_db()
        self.assertEqual(len(row.award_name), 500)
        with self.assertRaises(ProtectedError):
            self.category.delete()
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            self.create(key="inactive")
        self.create(key="null", award_category_id=None)
        self.assertEqual(
            self.client.get("/api/v1/awards/lookups/categories/").data["count"], 0
        )
        self.organization.is_active = False
        self.organization.save()
        with self.assertRaises(ValidationError):
            self.create(
                key="inactive-org",
                award_category_id=None,
                awarding_organization_id=self.organization.pk,
            )
        response = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(response.data["category_name"], self.category.category_name)

    def test_admin_scoping_and_category_governance(self):
        from types import SimpleNamespace

        from django.contrib import admin
        from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
        from django.test import RequestFactory

        from apps.awards.admin import AwardCategoryAdmin, StaffAwardAdmin

        row = self.create()
        request = RequestFactory().get("/admin/")
        request.user = self.root
        award_admin = StaffAwardAdmin(StaffAward, admin.site)
        master_admin = AwardCategoryAdmin(refs.AwardCategory, admin.site)
        self.assertTrue(award_admin.has_view_permission(request, row))
        self.assertFalse(award_admin.has_change_permission(request, row))
        self.assertFalse(award_admin.has_delete_permission(request, row))
        self.assertFalse(master_admin.has_delete_permission(request, self.category))
        self.category.is_active = False
        master_admin.save_model(
            request, self.category, SimpleNamespace(changed_data=["is_active"]), True
        )
        self.assertTrue(
            iam.ActivityAudit.objects.filter(
                module_code="AWARDS",
                entity_name="award_category",
                entity_id=str(self.category.pk),
            ).exists()
        )
        self.grant.delete()
        self.assertFalse(award_admin.has_view_permission(request, row))
        self.assertFalse(master_admin.has_change_permission(request, self.category))
        with self.assertRaises(DjangoPermissionDenied):
            master_admin.save_model(
                request, self.category, SimpleNamespace(changed_data=[]), True
            )

    def test_assignment_scope_and_cross_module_permissions(self):
        from apps.extracurricular import services as other_services

        with override_settings(EXTRACURRICULAR_ENABLED=True):
            call_command("seed_extracurricular", stdout=StringIO())
            for permission in iam.Permission.objects.filter(
                permission_code__startswith="EXTRACURRICULAR."
            ):
                iam.RolePermission.objects.create(role=self.role, permission=permission)
            category = refs.ExtraCurricularCategory.objects.create(
                category_code="OTHER", category_name="Other module"
            )
            other = other_services.save_activity(
                self.root,
                {
                    "event_name": "Other module record",
                    "extracurricular_category_id": category.pk,
                },
                context=self.context,
                key="other-module",
            )
            iam.RolePermission.objects.filter(
                role=self.role,
                permission__permission_code__startswith="EXTRACURRICULAR.",
            ).delete()
            self.assertEqual(
                self.client.get("/api/v1/extracurricular/activities/").data["count"], 0
            )
            self.assertEqual(
                self.client.get(
                    f"/api/v1/extracurricular/activities/{other.pk}/"
                ).status_code,
                404,
            )
            self.assertEqual(
                self.client.get(self.url + str(other.pk) + "/").status_code, 404
            )
        bad = dict(self.context, context_date=date(1900, 1, 1))
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                self.values | {"award_date": date(1900, 1, 1)},
                context=bad,
                key="old",
            )
        self.assertFalse(StaffAward.objects.exists())
