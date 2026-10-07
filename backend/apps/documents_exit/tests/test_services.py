import io
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.common_reference.models import DocumentType
from apps.core.models import ReferenceAuditEvent
from apps.documents_exit import integrations, storage
from apps.documents_exit import models as m
from apps.documents_exit import services as s
from apps.people_master.models import AccountLink, Student
from apps.people_master.tests.test_services import fixture
from apps.tenancy.models import Membership, ScopeGrant

from .providers import pdf


@override_settings(
    DOCUMENTS_EXIT_ENABLED=True,
    DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.clean",
    DOCUMENTS_CERTIFICATE_RENDERER="apps.documents_exit.tests.providers.pdf",
    DOCUMENTS_EXIT_CLEARANCE="apps.documents_exit.tests.providers.cleared",
)
class DocumentTests(TestCase):
    def setUp(self):
        fixture(self)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config = override_settings(
            DOCUMENTS_EXIT_INSTITUTIONS=[self.institution.pk],
            DOCUMENTS_STORAGE_ROOT=Path(self.tmp.name),
        )
        config.enable()
        self.addCleanup(config.disable)
        self.student = Student.objects.create(
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            student_number="M13",
            first_name="Student",
            display_name="Student",
            student_status="ACTIVE",
        )
        self.user = get_user_model().objects.create_user(username="m13student")
        self.user.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label="documents_exit",
                codename__in=[
                    "view_own_document",
                    "upload_own_document",
                    "request_certificate",
                    "access_restricted_file",
                ],
            )
        )
        Membership.objects.create(user=self.user, institution=self.institution)
        AccountLink.objects.create(user=self.user, student=self.student)
        self.kind = DocumentType.objects.create(
            document_code="M13", document_name="Test document"
        )
        self.certificate = s.certificate_type(
            actor=self.root, certificate_code="M13", certificate_name="Test certificate"
        )

    def upload(self):
        return SimpleUploadedFile("record.pdf", pdf(), content_type="application/pdf")

    def document(self, **values):
        return s.upload_document(
            actor=self.user,
            upload=self.upload(),
            document_type_id=self.kind.pk,
            **values,
        )

    def request(self):
        return s.request_certificate(
            actor=self.user, certificate_type_id=self.certificate.pk
        )

    def approved(self):
        obj = self.request()
        s.certificate_action(
            actor=self.root,
            pk=obj.pk,
            expected_status="SUBMITTED",
            action="review",
            reason="Review",
        )
        return s.certificate_action(
            actor=self.root,
            pk=obj.pk,
            expected_status="UNDER_REVIEW",
            action="approve",
            reason="Approved",
        )

    def test_upload_verify_download_journey(self):
        obj = self.document()
        self.assertEqual(obj.file_object.uploaded_by_user_id, self.user.pk)
        self.assertEqual(len(obj.file_object.checksum_sha256), 64)
        s.verify_document(
            actor=self.root,
            pk=obj.pk,
            expected_status="PENDING",
            target="VERIFIED",
            reason="Evidence checked",
        )
        obj.refresh_from_db()
        self.assertIsNotNone(obj.verified_at)
        client = APIClient()
        client.force_authenticate(self.user)
        result = client.get(f"/api/v1/documents/documents/{obj.pk}/download/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment", result["Content-Disposition"])
        self.assertTrue(b"".join(result.streaming_content).startswith(b"%PDF-"))
        result.close()

    def test_upload_validation_and_missing_scanner(self):
        for name in [
            "../file.pdf",
            "C:\\file.pdf",
            "file.exe.pdf",
            "file.exe",
            "bad\x00.pdf",
        ]:
            with self.assertRaises(ValidationError):
                storage.validate_name(name)
        for data, mime in [
            (b"", "application/pdf"),
            (b"MZscript", "application/pdf"),
            (pdf(), "image/png"),
        ]:
            with self.assertRaises(ValidationError):
                storage.validate_upload(
                    SimpleUploadedFile("record.pdf", data, content_type=mime)
                )
        with (
            override_settings(DOCUMENTS_MAX_BYTES=10),
            self.assertRaises(ValidationError),
        ):
            storage.validate_upload(self.upload())
        with (
            override_settings(DOCUMENTS_MALWARE_SCANNER=""),
            self.assertRaises(integrations.ProviderUnavailable),
        ):
            self.document()
        self.assertEqual(m.FileObject.objects.count(), 0)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_image_detection_and_scanner_rejection(self):
        from PIL import Image

        stream = io.BytesIO()
        Image.new("RGB", (2, 2)).save(stream, format="PNG")
        result = storage.validate_upload(
            SimpleUploadedFile("photo.png", stream.getvalue(), content_type="image/png")
        )
        self.assertEqual(result["mime"], "image/png")
        with (
            override_settings(
                DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.infected"
            ),
            self.assertRaises(ValidationError),
        ):
            self.document()

    def test_database_failure_cleans_physical_file(self):
        with (
            patch(
                "apps.documents_exit.services.audit",
                side_effect=RuntimeError("injected"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.document()
        self.assertEqual(m.FileObject.objects.count(), 0)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_nullable_document_uniqueness_and_failure_cleanup(self):
        self.document()
        self.document()
        self.document(document_number="same")
        before = set(Path(self.tmp.name).iterdir())
        with self.assertRaises(ValidationError):
            self.document(document_number="same")
        self.assertEqual(set(Path(self.tmp.name).iterdir()), before)
        self.assertEqual(m.StudentDocument.objects.count(), 3)

    def test_replacement_retains_previous_and_resets_verification(self):
        obj = self.document(document_number="original")
        old = obj.file_object
        s.verify_document(
            actor=self.root,
            pk=obj.pk,
            expected_status="PENDING",
            target="REJECTED",
            reason="Unreadable",
        )
        changed = s.update_document(
            actor=self.user,
            pk=obj.pk,
            expected_status="REJECTED",
            upload=self.upload(),
            document_number="corrected",
        )
        self.assertNotEqual(changed.file_object_id, old.pk)
        self.assertTrue(storage.backend().exists(old.storage_key))
        self.assertEqual(changed.verification_status, "PENDING")

    def test_illegal_verification_and_expiry(self):
        obj = self.document(expiry_date=timezone.localdate() - timedelta(days=1))
        with self.assertRaises(s.Conflict):
            s.verify_document(
                actor=self.root,
                pk=obj.pk,
                expected_status="PENDING",
                target="VERIFIED",
                reason="Check",
            )
        s.verify_document(
            actor=self.root,
            pk=obj.pk,
            expected_status="PENDING",
            target="EXPIRED",
            reason="Expiry job",
        )
        with self.assertRaises(NotFound):
            s.verify_document(
                actor=self.user,
                pk=obj.pk,
                expected_status="EXPIRED",
                target="PENDING",
                reason="Student",
            )

    def test_owned_scope_confidentiality_and_deleted_file(self):
        obj = self.document()
        other = get_user_model().objects.create_user(username="other")
        with self.assertRaises(NotFound):
            s.access_file(actor=other, resource="documents", pk=obj.pk)
        m.FileObject.objects.filter(pk=obj.file_object_id).update(
            confidentiality_level="HIGHLY_RESTRICTED"
        )
        with self.assertRaises(NotFound):
            s.access_file(actor=self.user, resource="documents", pk=obj.pk)
        s.access_file(
            actor=self.root,
            resource="documents",
            pk=obj.pk,
            delete=True,
            reason="Retain but withdraw access",
        )
        self.assertTrue(storage.backend().exists(obj.file_object.storage_key))
        with self.assertRaises(NotFound):
            s.access_file(actor=self.root, resource="documents", pk=obj.pk)

    def test_certificate_journey_idempotency_and_retention(self):
        obj = self.approved()
        issued = s.issue_certificate(
            actor=self.root, pk=obj.pk, reason="Approved template"
        )
        again = s.issue_certificate(actor=self.root, pk=obj.pk, reason="Retry")
        self.assertEqual(issued.file_object_id, again.file_object_id)
        self.assertEqual(m.FileObject.objects.count(), 1)
        stream, _file = s.access_file(
            actor=self.user, resource="certificates", pk=obj.pk
        )
        self.assertTrue(stream.read().startswith(b"%PDF"))
        stream.close()
        with self.assertRaises(s.Conflict):
            s.access_file(
                actor=self.root,
                resource="certificates",
                pk=obj.pk,
                delete=True,
                reason="No overwrite",
            )
        self.assertEqual(
            ReferenceAuditEvent.objects.filter(
                resource="m13_certificaterequest", after__event="certificate_issued"
            ).count(),
            1,
        )

    def test_issue_failure_never_marks_issued_or_orphans_file(self):
        obj = self.approved()
        with (
            override_settings(DOCUMENTS_CERTIFICATE_RENDERER=""),
            self.assertRaises(integrations.ProviderUnavailable),
        ):
            s.issue_certificate(actor=self.root, pk=obj.pk, reason="Issue")
        original = s.audit

        def fail(actor, obj, event, *args, **kwargs):
            if event == "certificate_issued":
                raise RuntimeError("injected")
            return original(actor, obj, event, *args, **kwargs)

        with (
            patch("apps.documents_exit.services.audit", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            s.issue_certificate(actor=self.root, pk=obj.pk, reason="Issue")
        obj.refresh_from_db()
        self.assertEqual(obj.request_status, "APPROVED")
        self.assertIsNone(obj.file_object_id)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_active_request_policy_and_inactive_type(self):
        self.request()
        with self.assertRaises(s.Conflict):
            self.request()
        with override_settings(
            DOCUMENTS_EXIT_POLICIES={
                str(self.institution.pk): {"allow_concurrent_requests": True}
            }
        ):
            self.request()
        s.certificate_type(
            actor=self.root,
            pk=self.certificate.pk,
            certificate_code="M13",
            certificate_name="Test certificate",
            is_active=False,
        )
        with self.assertRaises(NotFound):
            self.request()

    def test_self_approval_and_privileged_deny_paths(self):
        obj = self.request()
        for cap in ["approve_certificate", "review_certificate", "issue_certificate"]:
            self.user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="documents_exit", codename=cap
                )
            )
        member = Membership.objects.get(user=self.user)
        ScopeGrant.objects.create(membership=member, role="INSTITUTION_ADMIN")
        with self.assertRaises(PermissionDenied):
            s.certificate_action(
                actor=self.user,
                pk=obj.pk,
                expected_status="SUBMITTED",
                action="review",
                reason="Self",
            )
        with self.assertRaises(PermissionDenied):
            s.issue_certificate(actor=self.user, pk=obj.pk, reason="Self")
        with self.assertRaises(PermissionDenied):
            s.certificate_type(
                actor=self.user, certificate_code="BAD", certificate_name="Bad"
            )

    def test_approval_state_and_student_cancel(self):
        obj = self.request()
        with self.assertRaises(s.Conflict):
            s.certificate_action(
                actor=self.root,
                pk=obj.pk,
                expected_status="SUBMITTED",
                action="approve",
                reason="Skip",
            )
        s.certificate_action(
            actor=self.user,
            pk=obj.pk,
            expected_status="SUBMITTED",
            action="cancel",
            reason="Not needed",
        )
        with self.assertRaises(s.Conflict):
            s.issue_certificate(actor=self.root, pk=obj.pk, reason="Issue cancelled")

    def test_api_protected_fields_and_storage_redaction(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            "/api/v1/documents/certificates/submit/",
            {"certificate_type_id": self.certificate.pk, "request_status": "ISSUED"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        obj = self.document()
        response = client.get("/api/v1/documents/documents/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("storage_key", str(response.data))
        self.assertNotIn(obj.file_object.storage_key, str(response.data))
        self.assertEqual(
            client.patch(
                f"/api/v1/documents/documents/{obj.pk}/",
                {"verification_status": "VERIFIED"},
                format="json",
            ).status_code,
            405,
        )

    def test_sql_file_constraints(self):
        obj = self.document().file_object
        for changes in [{"file_size_bytes": 0}, {"checksum_sha256": "not-a-hash"}]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                m.FileObject.objects.filter(pk=obj.pk).update(**changes)
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.FileObject.objects.create(
                storage_provider="LOCAL_PRIVATE",
                storage_key=obj.storage_key,
                original_file_name="x.pdf",
                mime_type="application/pdf",
                file_size_bytes=1,
            )

    def test_storage_collision_preserves_existing_bytes(self):
        backend = storage.backend()
        key = "a" * 32 + ".pdf"
        backend.put(key, b"first")
        with self.assertRaises(FileExistsError):
            backend.put(key, b"second")
        with backend.open(key) as stream:
            self.assertEqual(stream.read(), b"first")

    def test_expiry_job_dry_run_and_idempotency(self):
        from django.core.management import call_command

        obj = self.document(expiry_date=timezone.localdate() - timedelta(days=1))
        output = io.StringIO()
        call_command("documents_expire", actor=self.root.pk, stdout=output)
        obj.refresh_from_db()
        self.assertEqual(obj.verification_status, "PENDING")
        call_command(
            "documents_expire", actor=self.root.pk, apply=True, stdout=io.StringIO()
        )
        call_command(
            "documents_expire", actor=self.root.pk, apply=True, stdout=io.StringIO()
        )
        obj.refresh_from_db()
        self.assertEqual(obj.verification_status, "EXPIRED")
        self.assertTrue(storage.backend().exists(obj.file_object.storage_key))

    def test_storage_reconciliation_counts_without_keys(self):
        import json

        from django.core.management import call_command

        orphan = "b" * 32 + ".pdf"
        storage.backend().put(orphan, b"unregistered test object")
        output = io.StringIO()
        call_command(
            "documents_storage_check",
            actor=self.root.pk,
            scan_orphans=True,
            stdout=output,
        )
        self.assertEqual(
            json.loads(output.getvalue())["unregistered_objects_in_sample"], 1
        )
        self.assertNotIn(orphan, output.getvalue())
        self.assertTrue(storage.backend().exists(orphan))

    def test_audit_endpoint_is_scoped_and_separate_from_student_reads(self):
        obj = self.document()
        client = APIClient()
        client.force_authenticate(self.user)
        self.assertEqual(
            client.get(f"/api/v1/documents/documents/{obj.pk}/audit/").status_code, 404
        )
        client.force_authenticate(self.root)
        result = client.get(f"/api/v1/documents/documents/{obj.pk}/audit/")
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(obj.file_object.storage_key, str(result.data))

    def test_storage_failure_after_put_cleans_orphan(self):
        original = storage.LocalPrivateStorage.put

        def broken(backend, key, data):
            original(backend, key, data)
            raise OSError("simulated ambiguous storage write")

        with (
            patch.object(storage.LocalPrivateStorage, "put", broken),
            self.assertRaises(integrations.ProviderUnavailable),
        ):
            self.document()
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
        self.assertEqual(m.FileObject.objects.count(), 0)

    def test_tampered_download_fails_integrity(self):
        obj = self.document()
        storage.backend().path(obj.file_object.storage_key).write_bytes(b"tampered")
        with self.assertRaises(s.Conflict):
            s.access_file(actor=self.user, resource="documents", pk=obj.pk)

    def test_native_file_timestamp_updates_on_soft_delete(self):
        obj = self.document()
        past = timezone.now() - timedelta(days=2)
        m.FileObject.objects.filter(pk=obj.file_object_id).update(updated_at=past)
        result = s.access_file(
            actor=self.root,
            resource="documents",
            pk=obj.pk,
            delete=True,
            reason="Retain record",
        )
        self.assertGreater(result.updated_at, past + timedelta(days=1))

    def test_multipart_upload_api(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            "/api/v1/documents/documents/upload/",
            {"upload": self.upload(), "document_type_id": self.kind.pk},
            format="multipart",
        )
        self.assertIn(response.status_code, (200, 201), response.data)
        self.assertEqual(m.StudentDocument.objects.count(), 1)
        self.assertNotIn("storage_key", str(response.data))

    def test_non_object_command_rejected(self):
        client = APIClient()
        client.force_authenticate(self.user)
        for payload in (1, [1], "invalid"):
            response = client.post(
                "/api/v1/documents/certificates/submit/", payload, format="json"
            )
            self.assertEqual(response.status_code, 400)
