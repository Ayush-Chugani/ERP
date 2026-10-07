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

from apps.documents_exit.models import FileObject
from apps.documents_exit.tests.providers import pdf
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink
from apps.professional_memberships import services as s
from apps.professional_memberships.models import (
    MembershipStatusHistory,
    StaffProfessionalMembership,
)
from apps.research_proposals.tests import test_module as base_fixture
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_profile import models as refs


@override_settings(
    PROFESSIONAL_MEMBERSHIPS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class MembershipTests(TestCase):
    def setUp(self):
        base_fixture.ProposalTests.setUp(self)
        call_command("seed_professional_memberships", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="PROFESSIONAL_MEMBERSHIPS."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.category = refs.MembershipType.objects.create(
            type_code="TEST", type_name="Synthetic category"
        )
        self.values = {
            "organization_id": self.organization.pk,
            "membership_type_id": self.category.pk,
            "membership_number": None,
            "membership_start_date": date(2026, 1, 1),
        }
        self.url = "/api/v1/professional-memberships/"

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
        self.assertEqual(StaffProfessionalMembership.objects.count(), 1)
        self.assertEqual(
            row.staff_activity.activity_type.activity_type_code, s.TYPE_CODE
        )
        with self.assertRaises(s.Conflict):
            self.create(membership_number="changed")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)

    def test_update_version_and_protected_context(self):
        row = self.create()
        token = s.version(row.pk)
        s.save_activity(
            self.root,
            {"membership_number": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"membership_number": "stale"},
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
                {"membership_number": "No"},
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
            {"membership_number": "Corrected"},
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
        self.assertTrue(StaffProfessionalMembership.objects.filter(pk=pk).exists())

    def test_scope_deny_self_and_export(self):
        row = self.create(membership_number="=HYPERLINK(1)")
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
        self.assertEqual(StaffProfessionalMembership.objects.count(), 1)
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
            permission_code="PROFESSIONAL_MEMBERSHIPS.ACTIVITY.READ"
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

    def test_configuration_idempotency_missing_and_disabled(self):
        count = iam.UserRoleAssignment.objects.count()
        call_command("seed_professional_memberships", stdout=StringIO())
        call_command("seed_professional_memberships", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        refs.ApprovalStatus.objects.filter(status_code="DRAFT").update(is_active=False)
        with self.assertRaises(ValidationError):
            self.create()
        with override_settings(PROFESSIONAL_MEMBERSHIPS_ENABLED=False):
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
                    "apps.professional_memberships.services.ActivityAttachment.objects.create",
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
            {"membership_number": "Changed"},
            activity_id=row.pk,
            expected_version=original,
        )
        s.save_activity(
            self.root,
            {"membership_number": self.values["membership_number"]},
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
                "apps.professional_memberships.services.record",
                side_effect=RuntimeError("synthetic"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(StaffProfessionalMembership.objects.count(), 0)
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
                    "activity": {"membership_number": "stale"},
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
                {"membership_number": "Should not save"},
                expected_version=s.version(row.pk),
            )
        row.refresh_from_db()
        self.assertEqual(row.membership_number, self.values["membership_number"])

    def test_lookup_and_master_permissions(self):
        self.create()
        path = "/api/v1/professional-memberships/lookups/"
        for resource in (
            "types",
            "organizations",
            "statuses",
            "years",
            "assignments",
        ):
            self.assertEqual(self.client.get(path + resource + "/").status_code, 200)
        admin = "/api/v1/professional-memberships/type-admin/"
        response = self.client.post(
            admin,
            {"type_code": "NEW", "type_name": "New category"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        iam.RolePermission.objects.filter(
            role=self.role,
            permission__permission_code="PROFESSIONAL_MEMBERSHIPS.MASTER.UPDATE",
        ).delete()
        self.assertEqual(self.client.get(admin).status_code, 403)
        self.assertEqual(
            self.client.post(
                admin, {"type_code": "NO", "type_name": "Denied"}, format="json"
            ).status_code,
            403,
        )

    def test_filters_reports_and_constant_queries(self):
        self.create()
        with CaptureQueriesContext(connection) as first:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
        for i in range(4):
            self.create(key=f"more-{i}", membership_number=f"Other-{i}")
        with CaptureQueriesContext(connection) as later:
            self.client.get(self.url)
        self.assertEqual(len(first), len(later))
        self.assertEqual(
            self.client.get(self.url, {"search": "Other"}).data["count"], 4
        )
        self.assertEqual(
            self.client.get(self.url, {"expiry_from": "invalid"}).status_code, 400
        )
        self.assertEqual(
            self.client.get(self.url, {"ordering": "password"}).status_code, 400
        )
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 5)
        iam.RolePermission.objects.filter(
            role=self.role,
            permission__permission_code="PROFESSIONAL_MEMBERSHIPS.ACTIVITY.EXPORT",
        ).delete()
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url).data["count"], 5)

    @override_settings(PROFESSIONAL_MEMBERSHIPS_EVENT_HANDLER="synthetic.adapter")
    def test_events_commit_retry_and_rollback(self):
        row = self.create()
        token = s.version(row.pk)
        with (
            patch("apps.professional_memberships.events.import_string") as load,
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
            patch("apps.professional_memberships.events.import_string") as load,
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
        self.assertEqual(
            MembershipStatusHistory.objects.filter(activity=row).count(), 2
        )

    def test_uniqueness_null_numbers_and_case_insensitive_database(self):
        from django.db import IntegrityError

        self.create(membership_number="  REF-1 ")
        with self.assertRaises(ValidationError):
            self.create(key="dup", membership_number="ref-1")
        other = refs.ExternalOrganization.objects.create(
            organization_name="Other organization"
        )
        self.create(
            key="other-org", organization_id=other.pk, membership_number="REF-1"
        )
        self.create(key="null1", membership_number=" ")
        row = self.create(key="null2", membership_number=None)
        self.assertIsNone(row.membership_number)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffProfessionalMembership.objects.filter(pk=row.pk).update(
                membership_number="REF-1"
            )
        self.assertEqual(StaffProfessionalMembership.objects.count(), 4)

    def test_dates_lifetime_required_and_partial_validation(self):
        from django.db import IntegrityError

        bad = [
            {"membership_expiry_date": date(2025, 1, 1)},
            {"membership_number": "X" * 151},
            {"organization_id": None},
            {"membership_type_id": None},
            {"membership_status": "WRONG"},
            {"is_lifetime_membership": True, "renewal_required": True},
            {
                "is_lifetime_membership": True,
                "membership_expiry_date": date(2028, 1, 1),
            },
            {"membership_status": "LIFETIME"},
            {"staff_activity_id": 123},
        ]
        for values in bad:
            with self.subTest(values=values):
                with self.assertRaises((ValidationError, NotFound)):
                    self.create(**values)
                self.assertFalse(StaffProfessionalMembership.objects.exists())
        row = self.create(is_lifetime_membership=True)
        self.assertEqual(row.membership_status, "LIFETIME")
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffProfessionalMembership.objects.filter(pk=row.pk).update(
                membership_expiry_date=date(2025, 1, 1)
            )
        with self.assertRaises(ValidationError):
            s.update_activity(
                self.root,
                row.pk,
                {"membership_status": "CANCELLED"},
                expected_version=s.version(row.pk),
            )
        response = self.client.patch(
            self.url + str(row.pk) + "/",
            {
                "activity": {"membership_number": "Updated"},
                "version": s.version(row.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_lifetime_membership"])

    def test_membership_transitions_renewal_and_audit(self):
        row = self.create(
            membership_expiry_date=date(2026, 2, 1), renewal_required=True
        )
        token = s.version(row.pk)
        s.membership_action(self.root, row.pk, "suspend", "Hold", token, "suspend")
        s.membership_action(self.root, row.pk, "suspend", "Hold", token, "suspend")
        with self.assertRaises(ValidationError):
            s.membership_action(
                self.root, row.pk, "reactivate", "Resume", s.version(row.pk), "resume"
            )
        s.membership_action(
            self.root, row.pk, "cancel", "Closed", s.version(row.pk), "cancel"
        )
        with self.assertRaises(ValidationError):
            s.membership_action(
                self.root,
                row.pk,
                "mark-lifetime",
                "Lifetime",
                s.version(row.pk),
                "lifetime",
            )
        renewable = self.create(
            key="renewable", membership_expiry_date=date(2026, 2, 1)
        )
        s.membership_action(
            self.root,
            renewable.pk,
            "renew",
            "Renewed",
            s.version(renewable.pk),
            "renew",
            timezone.localdate() + timedelta(days=365),
        )
        renewable.refresh_from_db()
        self.assertEqual(renewable.membership_status, "ACTIVE")
        s.membership_action(
            self.root,
            renewable.pk,
            "mark-lifetime",
            "Lifetime",
            s.version(renewable.pk),
            "life",
        )
        renewable.refresh_from_db()
        self.assertIsNone(renewable.membership_expiry_date)
        self.assertTrue(renewable.is_lifetime_membership)
        response = self.client.get(self.url + str(row.pk) + "/audit_history/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertGreaterEqual(response.data["count"], 3)

    def test_expiry_command_dry_run_idempotence_scopes_and_manual_states(self):
        today = timezone.localdate()
        active = self.create(membership_expiry_date=today - timedelta(days=1))
        suspended = self.create(
            key="suspended",
            membership_status="SUSPENDED",
            membership_expiry_date=today - timedelta(days=1),
        )
        lifetime = self.create(key="lifetime", is_lifetime_membership=True)
        due = self.create(
            key="due",
            membership_expiry_date=today + timedelta(days=10),
            renewal_required=True,
        )
        self.assertTrue(s.renewal_info(due)["renewal_due"])
        with override_settings(MEMBERSHIPS_RENEWAL_WINDOW_DAYS=5):
            self.assertFalse(s.renewal_info(due)["renewal_due"])
        call_command(
            "expire_professional_memberships",
            actor_id=self.root.pk,
            dry_run=True,
            stdout=StringIO(),
        )
        active.refresh_from_db()
        self.assertEqual(active.membership_status, "ACTIVE")
        with override_settings(MEMBERSHIPS_AUTO_EXPIRY_ENABLED=True):
            call_command(
                "expire_professional_memberships",
                actor_id=self.root.pk,
                stdout=StringIO(),
            )
            audit_count = iam.ActivityAudit.objects.filter(
                entity_id=str(active.pk), module_code=s.MODULE
            ).count()
            call_command(
                "expire_professional_memberships",
                actor_id=self.root.pk,
                stdout=StringIO(),
            )
            self.assertEqual(
                iam.ActivityAudit.objects.filter(
                    entity_id=str(active.pk), module_code=s.MODULE
                ).count(),
                audit_count,
            )
        active.refresh_from_db()
        suspended.refresh_from_db()
        lifetime.refresh_from_db()
        self.assertEqual(active.membership_status, "EXPIRED")
        self.assertEqual(suspended.membership_status, "SUSPENDED")
        self.assertEqual(lifetime.membership_status, "LIFETIME")
        self.assertEqual(
            self.client.get(self.url, {"renewal_due": "true"}).data["count"], 1
        )
        summary = self.client.get(self.url + "summary/").data
        self.assertEqual(summary["status_counts"]["EXPIRED"], 1)
        self.assertEqual(summary["expiring"]["30"], 1)

    def test_import_dry_run_errors_scope_and_idempotence(self):
        content = f"employee_assignment_id,context_date,organization_id,membership_type_id,membership_number\n{self.context['employee_assignment_id']},2026-01-01,{self.organization.pk},{self.category.pk},IMPORT-1\n"
        data = {"csv": content, "dry_run": True}
        response = self.client.post(
            self.url + "import/", data, format="json", HTTP_IDEMPOTENCY_KEY="batch"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["committed"])
        self.assertFalse(StaffProfessionalMembership.objects.exists())
        data["dry_run"] = False
        response = self.client.post(
            self.url + "import/", data, format="json", HTTP_IDEMPOTENCY_KEY="batch"
        )
        self.assertTrue(response.data["committed"], response.data)
        response = self.client.post(
            self.url + "import/", data, format="json", HTTP_IDEMPOTENCY_KEY="batch"
        )
        self.assertTrue(response.data["committed"], response.data)
        self.assertEqual(StaffProfessionalMembership.objects.count(), 1)
        response = self.client.post(
            self.url + "import/",
            data,
            format="json",
            HTTP_IDEMPOTENCY_KEY="duplicate-batch",
        )
        self.assertFalse(response.data["committed"])
        self.assertEqual(response.data["errors"][0]["row"], 2)
        self.grant.delete()
        response = self.client.post(
            self.url + "import/",
            {"csv": content.replace("IMPORT-1", "DENIED"), "dry_run": False},
            format="json",
            HTTP_IDEMPOTENCY_KEY="denied",
        )
        self.assertFalse(response.data["committed"])
        self.assertEqual(StaffProfessionalMembership.objects.count(), 1)

    def test_native_schema_and_retained_history(self):
        from importlib import import_module

        from django.apps import apps
        from django.db import DatabaseError

        self.create()
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE staff_professional_membership")
            ddl = cursor.fetchone()[1].lower()
            for part in (
                "uq_staff_membership_number",
                "chk_staff_membership_dates",
                "tinyint unsigned",
                "smallint unsigned",
                "enum('active','expired','suspended','cancelled','lifetime')",
            ):
                self.assertIn(part, ddl)
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE platform_professional_memberships_status_history SET remarks='tamper'"
            )
        with (
            self.assertRaises(RuntimeError),
            connection.schema_editor(atomic=False) as editor,
        ):
            import_module(
                "apps.professional_memberships.migrations.0002_retain_status_history"
            ).reverse(apps, editor)

    def test_lifecycle_api_permission_versions_and_no_patch_bypass(self):
        row = self.create()
        url = self.url + str(row.pk) + "/"
        bad = self.client.patch(
            url,
            {
                "version": s.version(row.pk),
                "activity": {"membership_status": "SUSPENDED"},
            },
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        data = {
            "action": "suspend",
            "remarks": "Administrative hold",
            "version": s.version(row.pk),
        }
        response = self.client.post(
            url + "lifecycle/", data, format="json", HTTP_IDEMPOTENCY_KEY="api-suspend"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["membership_status"], "SUSPENDED")
        response = self.client.post(
            url + "lifecycle/", data, format="json", HTTP_IDEMPOTENCY_KEY="api-suspend"
        )
        self.assertEqual(response.status_code, 200, response.data)
        iam.RolePermission.objects.filter(
            role=self.role,
            permission__permission_code="PROFESSIONAL_MEMBERSHIPS.ACTIVITY.VERIFY",
        ).delete()
        response = self.client.get(url)
        self.assertEqual(response.data["membership_actions"], [])
        denied = self.client.post(
            url + "lifecycle/",
            {
                "action": "cancel",
                "remarks": "Denied",
                "version": response.data["version"],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="denied-action",
        )
        self.assertEqual(denied.status_code, 403)
        row.refresh_from_db()
        self.assertEqual(row.membership_status, "SUSPENDED")

    def test_all_optional_references_filters_and_put_contract(self):
        role = refs.RoleType.objects.create(
            role_code="ROLE", role_name="Committee member"
        )
        level = refs.ParticipationLevel.objects.create(
            level_code="NATIONAL", level_name="National"
        )
        row = self.create(
            role_type_id=role.pk,
            participation_level_id=level.pk,
            membership_number=chr(0x1F600) * 150,
            membership_expiry_date=date(2030, 1, 1),
            renewal_required=True,
        )
        for query in (
            {"organization": self.organization.pk},
            {"membership_type": self.category.pk},
            {"role_type": role.pk},
            {"participation_level": level.pk},
            {"membership_status": "ACTIVE"},
            {"renewal_required": "true"},
            {"is_lifetime_membership": "false"},
            {"start_from": "2026-01-01", "start_to": "2026-01-01"},
            {"expiry_from": "2029-01-01", "expiry_to": "2030-01-01"},
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.url, query).data["count"], 1)
        detail = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(detail.data["role_name"], role.role_name)
        self.assertEqual(detail.data["participation_level_name"], level.level_name)
        response = self.client.put(
            self.url + str(row.pk) + "/",
            {
                "version": detail.data["version"],
                "activity": {
                    "organization_id": self.organization.pk,
                    "membership_type_id": self.category.pk,
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["membership_start_date"])
        self.assertIsNone(response.data["role_type"])
        self.assertFalse(response.data["renewal_required"])
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            self.create(key="inactive")

    def test_import_batch_error_rolls_back_valid_rows_and_receipts(self):
        from apps.professional_memberships.imports import import_csv

        row = f"{self.context['employee_assignment_id']},2026-01-01,{self.organization.pk},{self.category.pk},SAME"
        content = (
            "employee_assignment_id,context_date,organization_id,membership_type_id,membership_number\n"
            + row
            + "\n"
            + row
            + "\n"
        )
        result = import_csv(self.root, {"csv": content, "dry_run": False}, "duplicates")
        self.assertFalse(result["committed"])
        self.assertEqual(result["errors"][0]["row"], 3)
        self.assertFalse(StaffProfessionalMembership.objects.exists())
        self.assertFalse(ActivityCommandReceipt.objects.exists())

    def test_admin_is_scoped_readonly_and_master_changes_audited(self):
        from types import SimpleNamespace

        from django.contrib import admin
        from django.test import RequestFactory

        from apps.professional_memberships.admin import (
            MembershipTypeAdmin,
            StaffProfessionalMembershipAdmin,
        )

        row = self.create()
        request = RequestFactory().get("/admin/")
        request.user = self.root
        view = StaffProfessionalMembershipAdmin(StaffProfessionalMembership, admin.site)
        self.assertTrue(view.has_view_permission(request, row))
        self.assertFalse(view.has_change_permission(request, row))
        self.assertFalse(view.has_delete_permission(request, row))
        invalid = self.client.patch(
            "/api/v1/professional-memberships/type-admin/not-a-number/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(invalid.status_code, 404)
        master = MembershipTypeAdmin(refs.MembershipType, admin.site)
        self.category.is_active = False
        master.save_model(
            request, self.category, SimpleNamespace(changed_data=["is_active"]), True
        )
        self.assertTrue(
            iam.ActivityAudit.objects.filter(
                module_code=s.MODULE, entity_name="membership_type"
            ).exists()
        )
        self.grant.delete()
        self.assertFalse(view.has_view_permission(request, row))
        self.assertFalse(master.has_change_permission(request, self.category))
