import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.common_reference.models import DocumentType
from apps.documents_exit.models import FileObject
from apps.documents_exit.tests.providers import pdf
from apps.evidence import services as s
from apps.evidence.models import (
    EvidenceCommandReceipt,
    EvidenceDocument,
    EvidenceDocumentAudit,
    EvidenceDocumentTag,
    EvidenceDocumentVersion,
    EvidenceTag,
)
from apps.identity_access import models as iam
from apps.research_proposals.tests import test_module as base_fixture
from apps.staff_activities.models import StaffActivity
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    ConfidentialityLevel,
    VerificationStatus,
)


@override_settings(
    EVIDENCE_ENABLED=True,
    DOCUMENTS_EXIT_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class EvidenceTests(TestCase):
    def setUp(self):
        base_fixture.ProposalTests.setUp(self)
        for index, code in enumerate(
            ("PUBLIC", "INTERNAL", "RESTRICTED", "CONFIDENTIAL", "HIGHLY_RESTRICTED"), 1
        ):
            ConfidentialityLevel.objects.get_or_create(
                level_code=code,
                defaults={
                    "confidentiality_level_id": index,
                    "level_name": code.replace("_", " ").title(),
                    "display_order": index * 10,
                },
            )
        call_command("seed_evidence", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="EVIDENCE."
        ):
            iam.RolePermission.objects.get_or_create(
                role=self.role, permission=permission
            )
        kind = ActivityType.objects.create(
            activity_type_code="M33_TEST",
            activity_type_name="M33 synthetic",
            activity_group="OTHER",
        )
        self.parent = StaffActivity.objects.create(
            employee=self.employee,
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            activity_type=kind,
            activity_title="Synthetic activity",
            approval_status=ApprovalStatus.objects.get(status_code="DRAFT"),
            verification_status=VerificationStatus.objects.get(status_code="PENDING"),
            created_by_user=self.root,
        )
        self.document_type = DocumentType.objects.create(
            document_code="M33", document_name="M33 document"
        )
        self.level = ConfidentialityLevel.objects.get(level_code="RESTRICTED")
        self.values = {
            "staff_activity_id": self.parent.pk,
            "document_type_id": self.document_type.pk,
            "confidentiality_level_id": self.level.pk,
            "document_title": "Synthetic evidence",
        }
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        configured = override_settings(
            DOCUMENTS_STORAGE_ROOT=Path(self.temp.name),
            DOCUMENTS_EXIT_INSTITUTIONS=(self.institution.pk,),
            DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.clean",
        )
        configured.enable()
        self.addCleanup(configured.disable)
        self.url = "/api/v1/evidence/documents/"

    def upload(self, name="evidence.pdf"):
        return SimpleUploadedFile(name, pdf(), content_type="application/pdf")

    def create(self, key="create", **values):
        return s.create_evidence_with_file(
            actor=self.root, values=self.values | values, upload=self.upload(), key=key
        )

    def reviewer(self, name="reviewer"):
        user = get_user_model().objects.create_user(username=name)
        iam.UserRoleAssignment.objects.create(
            user=user,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        return user

    def test_creation_idempotence_and_native_invariants(self):
        row = self.create()
        again = self.create()
        self.assertEqual(row.pk, again.pk)
        self.assertEqual(EvidenceDocument.objects.count(), 1)
        content = EvidenceDocumentVersion.objects.get(evidence_document=row)
        self.assertEqual(content.version_number, 1)
        self.assertTrue(content.is_current)
        self.assertEqual(content.current_document_id, row.pk)
        self.assertEqual(FileObject.objects.count(), 1)
        self.assertEqual(
            list(EvidenceDocumentAudit.objects.values_list("action_code", flat=True)),
            ["CREATE", "UPLOAD"],
        )
        with self.assertRaises(s.Conflict):
            self.create(document_title="Changed key body")
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM evidence_document_version")
            self.assertEqual(len(cursor.fetchall()), 9)
        with self.assertRaises(DatabaseError), transaction.atomic():
            EvidenceDocumentVersion.objects.create(
                evidence_document=row,
                version_number=2,
                file_object=content.file_object,
                uploaded_by_user=self.root,
            )

    def test_failed_audit_and_invalid_metadata_cleanup(self):
        with (
            patch(
                "apps.evidence.audit.write",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(EvidenceDocument.all_objects.count(), 0)
        self.assertEqual(FileObject.objects.count(), 0)
        self.assertEqual(list(Path(self.temp.name).glob("*")), [])
        with self.assertRaises(ValidationError):
            self.create(
                document_issue_date=date(2026, 2, 1), expiry_date=date(2026, 1, 1)
            )
        with self.assertRaises(ValidationError):
            self.create(tags=[999999])
        self.assertEqual(FileObject.objects.count(), 0)
        self.assertEqual(list(Path(self.temp.name).glob("*")), [])

    def test_workflow_replacement_history_and_access_audit(self):
        row = self.create()
        verifier = self.reviewer()
        approver = self.reviewer("approver")
        with self.assertRaises(NotFound):
            s.workflow(
                actor=self.root,
                document_id=row.pk,
                action="verify",
                remarks="Self",
                expected_version=s.version(row),
                key="self",
            )
        s.workflow(
            actor=verifier,
            document_id=row.pk,
            action="verify",
            remarks="Checked",
            expected_version=s.version(row),
            key="verify",
        )
        s.workflow(
            actor=approver,
            document_id=row.pk,
            action="approve",
            remarks="Approved",
            expected_version=s.version(row),
            key="approve",
        )
        old = EvidenceDocumentVersion.objects.get(evidence_document=row)
        token = s.version(row)
        s.replace_evidence_file(
            actor=self.root,
            document_id=row.pk,
            upload=self.upload("new.pdf"),
            change_reason="Corrected evidence",
            expected_version=token,
            key="replace",
        )
        s.replace_evidence_file(
            actor=self.root,
            document_id=row.pk,
            upload=self.upload("new.pdf"),
            change_reason="Corrected evidence",
            expected_version=token,
            key="replace",
        )
        row.refresh_from_db()
        old.refresh_from_db()
        self.assertEqual(row.current_version_number, 2)
        self.assertFalse(old.is_current)
        self.assertEqual(row.verification_status.status_code, "PENDING")
        self.assertEqual(row.approval_status.status_code, "DRAFT")
        self.assertIsNone(row.verified_at)
        self.assertIsNone(row.approved_by_user_id)
        self.assertEqual(
            EvidenceDocumentVersion.objects.filter(
                evidence_document=row, is_current=True
            ).count(),
            1,
        )
        for n, preview in ((1, False), (2, True)):
            stream, _file = s.access_file(
                actor=self.root, document_id=row.pk, version_number=n, preview=preview
            )
            self.assertEqual(stream.read(), pdf())
            stream.close()
        actions = set(
            EvidenceDocumentAudit.objects.filter(evidence_document=row).values_list(
                "action_code", flat=True
            )
        )
        self.assertTrue(
            {"VERIFY", "APPROVE", "REPLACE", "PREVIEW", "DOWNLOAD", "ACCESS_DENIED"}
            <= actions
        )
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE evidence_document_version SET change_reason='tampered' WHERE evidence_document_version_id=%s",
                [old.pk],
            )
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "DELETE FROM evidence_document_audit WHERE evidence_document_id=%s",
                [row.pk],
            )

    def test_metadata_diffs_tags_and_mass_assignment(self):
        tag = EvidenceTag.objects.create(tag_code="CERTIFICATE", tag_name="Certificate")
        row = self.create()
        token = s.version(row)
        s.update_evidence_metadata(
            actor=self.root,
            document_id=row.pk,
            values={"document_title": "New title", "tags": [tag.pk]},
            expected_version=token,
        )
        event = EvidenceDocumentAudit.objects.filter(
            evidence_document=row, action_code="UPDATE_METADATA"
        ).get()
        self.assertEqual(set(event.after_values), {"document_title", "tags"})
        self.assertEqual(event.before_values["tags"], [])
        with self.assertRaises(s.Conflict):
            s.update_evidence_metadata(
                actor=self.root, document_id=row.pk, values={}, expected_version=token
            )
        with self.assertRaises(ValidationError):
            s.update_evidence_metadata(
                actor=self.root,
                document_id=row.pk,
                values={"approved_by_user_id": self.root.pk},
                expected_version=s.version(row),
            )
        self.assertEqual(
            EvidenceDocumentTag.objects.filter(evidence_document=row).count(), 1
        )

    def test_soft_delete_restore_retains_files_and_is_idempotent(self):
        row = self.create()
        token = s.version(row)
        for _ in range(2):
            s.deletion(
                actor=self.root,
                document_id=row.pk,
                restore=False,
                reason="Withdraw duplicate",
                expected_version=token,
                key="delete",
            )
        self.assertEqual(EvidenceDocument.objects.count(), 0)
        self.assertEqual(EvidenceDocument.all_objects.count(), 1)
        self.assertEqual(FileObject.objects.count(), 1)
        with self.assertRaises(NotFound):
            s.access_file(actor=self.root, document_id=row.pk)
        s.deletion(
            actor=self.root,
            document_id=row.pk,
            restore=True,
            reason="Restore record",
            expected_version=s.version(row),
            key="restore",
        )
        self.assertEqual(EvidenceDocument.objects.count(), 1)
        self.assertEqual(
            EvidenceDocumentAudit.objects.filter(action_code="SOFT_DELETE").count(), 1
        )

    def test_metadata_only_reviewer_and_unknown_classification_deny(self):
        row = self.create()
        viewer = self.reviewer()
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="EVIDENCE.FILE.READ"
        ).delete()
        self.client.force_authenticate(viewer)
        response = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("download", response.data["actions"])
        self.assertEqual(
            self.client.get(self.url + str(row.pk) + "/download/").status_code, 404
        )
        self.assertEqual(
            EvidenceDocumentAudit.objects.filter(action_code="ACCESS_DENIED").count(), 1
        )
        with override_settings(EVIDENCE_CLASSIFICATIONS={}):
            self.assertEqual(self.client.get(self.url).data["count"], 0)
            self.assertEqual(
                self.client.get(self.url + str(row.pk) + "/").status_code, 404
            )

    def test_api_upload_read_history_headers_and_query_count(self):
        response = self.client.post(
            self.url,
            {"metadata": json.dumps(self.values), "file": self.upload()},
            format="multipart",
            HTTP_IDEMPOTENCY_KEY="api",
        )
        self.assertEqual(response.status_code, 201, response.data)
        identifier = response.data["evidence_document_id"]
        response = self.client.get(self.url + identifier + "/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), pdf())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        for suffix in ("versions/", "audit/"):
            response = self.client.get(self.url + identifier + "/" + suffix)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertNotIn("storage_key", str(response.data))
        counts = []
        for total in (1, 5):
            for i in range(1, total):
                self.create(key=f"many-{i}")
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            counts.append(len(captured))
        self.assertEqual(counts[0], counts[1])

    def test_scanner_signature_filename_and_size_rejections(self):
        uploads = [
            SimpleUploadedFile("bad.html", b"<html>script</html>"),
            SimpleUploadedFile("bad.pdf", b"not a pdf"),
            SimpleUploadedFile("double.exe.pdf", pdf()),
        ]
        for i, upload in enumerate(uploads):
            with self.subTest(i=i), self.assertRaises(ValidationError):
                s.create_evidence_with_file(
                    actor=self.root, values=self.values, upload=upload, key=f"bad-{i}"
                )
        with (
            override_settings(DOCUMENTS_MAX_BYTES=5),
            self.assertRaises(ValidationError),
        ):
            self.create()
        with (
            patch("apps.documents_exit.storage.invoke", return_value=False),
            self.assertRaises(ValidationError),
        ):
            self.create()
        self.assertFalse(FileObject.objects.exists())
        self.assertFalse(EvidenceDocument.objects.exists())

    def test_legacy_dry_run_replay_conflict_and_containment(self):
        from apps.evidence.imports import legacy_import

        source = Path(self.temp.name) / "legacy"
        source.mkdir()
        (source / "certificate.pdf").write_bytes(pdf())
        entries = [
            {
                "source_id": "old-17",
                "path": "certificate.pdf",
                "metadata": self.values,
                "original_timestamps": {"uploaded_at": "2020-01-01"},
                "original_status": "APPROVED",
            }
        ]
        result = legacy_import(
            actor=self.root,
            entries=entries,
            root=source,
            namespace="test",
            dry_run=True,
        )
        self.assertEqual(result["failed"], 0, result)
        self.assertFalse(EvidenceDocument.objects.exists())
        result = legacy_import(
            actor=self.root,
            entries=entries,
            root=source,
            namespace="test",
            dry_run=False,
        )
        self.assertEqual(result["failed"], 0, result)
        self.assertEqual(result["rows"][0]["status"], "created")
        result = legacy_import(
            actor=self.root,
            entries=entries,
            root=source,
            namespace="test",
            dry_run=False,
        )
        self.assertEqual(result["rows"][0]["status"], "replayed", result)
        self.assertEqual(
            EvidenceDocument.objects.get().approval_status.status_code, "DRAFT"
        )
        entries[0]["metadata"] = self.values | {"document_title": "Changed legacy row"}
        self.assertEqual(
            legacy_import(
                actor=self.root,
                entries=entries,
                root=source,
                namespace="test",
                dry_run=True,
            )["failed"],
            1,
        )
        entries[0]["path"] = "../outside.pdf"
        self.assertEqual(
            legacy_import(
                actor=self.root,
                entries=entries,
                root=source,
                namespace="test",
                dry_run=True,
            )["failed"],
            1,
        )
        self.assertEqual(EvidenceDocument.objects.count(), 1)
        self.assertEqual(
            EvidenceCommandReceipt.objects.get().provenance["original_status"],
            "APPROVED",
        )

    def test_expiry_boundaries_dedup_delivery_failure_and_cursor(self):
        from apps.evidence.models import EvidenceExpiryNotice
        from apps.evidence.tasks import expiry_notices

        row = self.create(expiry_date=date(2026, 2, 7))
        future = self.create(key="far-future", expiry_date=date(2027, 2, 7))
        result = expiry_notices(actor=self.root, as_of=date(2026, 1, 31))
        self.assertEqual(result["candidates"], 1)
        self.assertFalse(EvidenceExpiryNotice.objects.exists())
        with (
            override_settings(EVIDENCE_NOTIFICATION_HANDLER="test.adapter"),
            patch("apps.evidence.tasks.import_string") as adapter,
        ):
            adapter.return_value.side_effect = RuntimeError("unavailable")
            result = expiry_notices(
                actor=self.root, as_of=date(2026, 1, 31), dry_run=False
            )
            self.assertEqual(result["failed"], 1)
            adapter.return_value.side_effect = None
            result = expiry_notices(
                actor=self.root, as_of=date(2026, 1, 31), dry_run=False
            )
            self.assertEqual(result["delivered"], 1)
            event = adapter.return_value.call_args.kwargs["event"]
            self.assertEqual(
                set(event), {"event_id", "document_id", "actor_id", "threshold_days"}
            )
            self.assertEqual(event["threshold_days"], 7)
            result = expiry_notices(
                actor=self.root, as_of=date(2026, 2, 1), dry_run=False
            )
            self.assertEqual(result["delivered"], 0)
            result = expiry_notices(
                actor=self.root, as_of=date(2026, 2, 8), dry_run=False
            )
            self.assertEqual(result["delivered"], 1)
        self.assertEqual(EvidenceExpiryNotice.objects.count(), 2)
        result = expiry_notices(
            actor=self.root, as_of=date(2026, 1, 31), after_id=row.pk
        )
        self.assertEqual(result["candidates"], 0)
        self.assertNotEqual(row.pk, future.pk)

    def test_report_export_tag_admin_and_deleted_scope(self):
        tag = EvidenceTag.objects.create(tag_code="REPORT", tag_name="Reporting")
        first = self.create(
            document_title="=HYPERLINK(x)", tags=[tag.pk], expiry_date=date(2020, 1, 1)
        )
        self.create(key="second", tags=[tag.pk])
        response = self.client.get(self.url + "summary/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["version_count"], 2)
        self.assertEqual(response.data["expired"], 1)
        response = self.client.get(self.url + "export/")
        self.assertIn("'=HYPERLINK", b"".join(response.streaming_content).decode())
        response = self.client.patch(
            "/api/v1/evidence/tags/" + str(tag.pk) + "/",
            {"tag_name": "Changed tag"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(
            "/api/v1/evidence/tags/999999/", {"tag_name": "Missing"}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        s.deletion(
            actor=self.root,
            document_id=first.pk,
            restore=False,
            reason="Archive",
            expected_version=s.version(first),
            key="delete",
        )
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"deleted": "1"}).data["count"], 1)

    def test_invalid_actions_classifier_change_and_admin_scope(self):
        from django.contrib.admin import AdminSite
        from django.test import RequestFactory

        from apps.evidence.admin import EvidenceDocumentAdmin

        row = self.create()
        reviewer = self.reviewer()
        with self.assertRaises(ValidationError):
            s.workflow(
                actor=reviewer,
                document_id=row.pk,
                action="approve",
                remarks="Too early",
                expected_version=s.version(row),
                key="early",
            )
        s.workflow(
            actor=reviewer,
            document_id=row.pk,
            action="reject-verification",
            remarks="Needs correction",
            expected_version=s.version(row),
            key="reject-verification",
        )
        s.update_evidence_metadata(
            actor=self.root,
            document_id=row.pk,
            values={"description": "Corrected"},
            expected_version=s.version(row),
        )
        s.workflow(
            actor=reviewer,
            document_id=row.pk,
            action="verify",
            remarks="Checked",
            expected_version=s.version(row),
            key="verify",
        )
        s.workflow(
            actor=reviewer,
            document_id=row.pk,
            action="reject-approval",
            remarks="Needs evidence",
            expected_version=s.version(row),
            key="reject-approval",
        )
        req = RequestFactory().get("/")
        req.user = self.root
        admin = EvidenceDocumentAdmin(EvidenceDocument, AdminSite())
        self.assertTrue(admin.has_view_permission(req, row))
        self.assertFalse(admin.has_change_permission(req, row))
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="EVIDENCE.LEVEL_RESTRICTED.READ"
        ).delete()
        self.assertFalse(admin.has_view_permission(req, row))
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        with self.assertRaises(NotFound):
            s.access_file(actor=self.root, document_id=row.pk)

    def test_confidentiality_change_needs_explicit_right_and_keeps_old_file_protection(
        self,
    ):
        row = self.create()
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="EVIDENCE.CLASSIFICATION.UPDATE"
        ).delete()
        public = ConfidentialityLevel.objects.get(level_code="PUBLIC")
        with self.assertRaises(NotFound):
            s.update_evidence_metadata(
                actor=self.root,
                document_id=row.pk,
                values={"confidentiality_level_id": public.pk},
                expected_version=s.version(row),
            )
        row.refresh_from_db()
        self.assertEqual(row.confidentiality_level_id, self.level.pk)

    def test_seed_idempotence_health_and_runtime_disabled(self):
        before = iam.RolePermission.objects.count()
        call_command("seed_evidence", stdout=StringIO())
        self.assertEqual(iam.RolePermission.objects.count(), before)
        output = StringIO()
        call_command("evidence_health", stdout=output)
        self.assertEqual(
            json.loads(output.getvalue())["current_version_invariant_failures"], 0
        )
        with override_settings(EVIDENCE_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)
            with self.assertRaises(NotFound):
                self.create()

    def test_failed_replacement_and_failed_access_audit_leave_no_new_content(self):
        row = self.create()
        token = s.version(row)
        with patch(
            "apps.evidence.audit.write", side_effect=RuntimeError("audit unavailable")
        ):
            with self.assertRaises(RuntimeError):
                s.replace_evidence_file(
                    actor=self.root,
                    document_id=row.pk,
                    upload=self.upload("new.pdf"),
                    change_reason="Correction",
                    expected_version=token,
                    key="fail",
                )
            with self.assertRaises(RuntimeError):
                s.access_file(actor=self.root, document_id=row.pk)
        self.assertEqual(s.version(row), token)
        self.assertEqual(
            EvidenceDocumentVersion.objects.filter(is_current=True).count(), 1
        )
        self.assertEqual(FileObject.objects.count(), 1)
        self.assertEqual(len(list(Path(self.temp.name).glob("*"))), 1)
        file = FileObject.objects.get()
        (Path(self.temp.name) / file.storage_key).write_bytes(b"tampered")
        with self.assertRaises(s.Conflict):
            s.access_file(actor=self.root, document_id=row.pk)
        self.assertFalse(
            EvidenceDocumentAudit.objects.filter(action_code="DOWNLOAD").exists()
        )

    def test_explicit_deny_hides_lists_detail_reports_and_binary(self):
        row = self.create()
        self.client.force_authenticate(self.root)
        iam.UserPermissionOverride.objects.create(
            user=self.root,
            permission=iam.Permission.objects.get(
                permission_code="EVIDENCE.DOCUMENT.READ"
            ),
            permission_effect="DENY",
            justification="Synthetic deny",
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        for suffix in ("", "versions/", "audit/", "download/", "preview/"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    self.client.get(f"{self.url}{row.pk}/{suffix}").status_code, 404
                )

    def test_end_to_end_acceptance_lifecycle(self):
        self.client.force_authenticate(self.root)
        response = self.client.post(
            self.url,
            {"metadata": json.dumps(self.values), "file": self.upload()},
            HTTP_IDEMPOTENCY_KEY="accept-create",
        )
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["evidence_document_id"]
        endpoint = f"{self.url}{pk}/"
        reviewer = self.reviewer("accept-reviewer")
        self.client.force_authenticate(reviewer)
        for action in ("verify", "approve"):
            token = self.client.get(endpoint).data["version"]
            result = self.client.post(
                endpoint + action + "/",
                data=json.dumps({"remarks": "Acceptance review", "version": token}),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="accept-" + action,
            )
            self.assertEqual(result.status_code, 200, result.data)
        self.client.force_authenticate(self.root)
        token = self.client.get(endpoint).data["version"]
        result = self.client.post(
            endpoint + "replace-file/",
            {
                "file": self.upload("corrected.pdf"),
                "change_reason": "Acceptance replacement",
                "version": token,
            },
            HTTP_IDEMPOTENCY_KEY="accept-replace",
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["verification"], "PENDING")
        download = self.client.get(endpoint + "versions/1/download/")
        self.assertEqual(download.status_code, 200)
        # Test client iteration closes the stream with transaction-safe signals.
        self.assertEqual(b"".join(download.streaming_content), pdf())
        for action in ("soft-delete", "restore"):
            row = EvidenceDocument.all_objects.get(pk=pk)
            result = self.client.post(
                endpoint + action + "/",
                data=json.dumps(
                    {"reason": "Acceptance lifecycle", "version": s.version(row)}
                ),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="accept-" + action,
            )
            self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.client.get(endpoint).status_code, 200)
        self.assertEqual(
            EvidenceDocumentVersion.objects.filter(evidence_document_id=pk).count(), 2
        )
