from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.communication import models as m
from apps.communication import selectors as q
from apps.communication import services as s
from apps.documents_exit import models as files
from apps.documents_exit.tests.providers import pdf
from apps.organization.models import Institution, Programme
from apps.people_master.models import AccountLink, Student
from apps.people_master.tests.test_services import fixture
from apps.tenancy.models import Membership, ScopeGrant


class Setup:
    def setUp(self):
        fixture(self)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = override_settings(
            COMMUNICATION_ENABLED=True,
            COMMUNICATION_INSTITUTIONS=[self.institution.pk],
            DOCUMENTS_EXIT_ENABLED=True,
            DOCUMENTS_EXIT_INSTITUTIONS=[self.institution.pk],
            DOCUMENTS_STORAGE_ROOT=Path(self.tmp.name),
            DOCUMENTS_MALWARE_SCANNER="apps.documents_exit.tests.providers.clean",
        )
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.author = get_user_model().objects.create_user(username="author")
        self.reader = get_user_model().objects.create_user(username="reader")
        self.membership = Membership.objects.create(
            user=self.author, institution=self.institution
        )
        ScopeGrant.objects.create(membership=self.membership, role="INSTITUTION_ADMIN")
        Membership.objects.create(user=self.reader, institution=self.institution)
        self.author.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label__in=["communication", "documents_exit"]
            )
        )
        self.kind = s.write_type(
            actor=self.root, type_code="NOTICE", type_name="Notice"
        )
        self.now = timezone.now().replace(microsecond=0)

    def draft(self, **kw):
        fields = {
            "institution_id": self.institution.pk,
            "department_id": self.department.pk,
            "announcement_type_id": self.kind.pk,
            "title": "Notice",
            "description": "<script>do not execute</script>",
            "publish_from": self.now - timedelta(hours=1),
            "publish_to": self.now + timedelta(hours=1),
            "audience_type": "ALL",
        }
        fields.update(kw)
        return s.write(actor=self.author, **fields)

    def action(self, obj, action, actor=None):
        return s.workflow(
            actor=actor or self.author,
            pk=obj.pk,
            action=action,
            expected_version=q.version(obj),
            reason="Reviewed",
        )

    def approved(self, **kw):
        obj = self.draft(**kw)
        self.action(obj, "submit")
        return self.action(obj, "approve", self.root)

    def upload(self, obj, level="INTERNAL"):
        return s.upload_attachment(
            actor=self.author,
            pk=obj.pk,
            expected_version=q.version(obj),
            upload=SimpleUploadedFile(
                "notice.pdf", pdf(), content_type="application/pdf"
            ),
            level=level,
        )


class DomainTests(Setup, TestCase):
    def test_baseline_native_schema_and_extensions(self):
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE announcement")
            ddl = cursor.fetchone()[1]
            self.assertIn(
                "enum('DRAFT','PENDING','APPROVED','REJECTED','ARCHIVED')", ddl
            )
            self.assertIn("`institution_id` smallint unsigned NOT NULL", ddl)
            self.assertIn("`publish_from` datetime NOT NULL", ddl)
            cursor.execute("SHOW CREATE TABLE announcement_attachment")
            ddl = cursor.fetchone()[1]
            self.assertIn("PRIMARY KEY (`announcement_id`,`file_object_id`)", ddl)
            self.assertNotIn("AUTO_INCREMENT", ddl)
            for table in ["announcement_programme_target", "announcement_user_target"]:
                cursor.execute(
                    "SELECT TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                    [table],
                )
                self.assertEqual(cursor.fetchone()[0], "utf8mb4_unicode_ci")

    def test_time_boundaries(self):
        obj = self.approved(
            publish_from=self.now, publish_to=self.now + timedelta(seconds=1)
        )
        self.assertFalse(
            q.can_view(self.reader, obj.pk, self.now - timedelta(seconds=1))
        )
        self.assertTrue(q.can_view(self.reader, obj.pk, self.now))
        self.assertFalse(
            q.can_view(self.reader, obj.pk, self.now + timedelta(seconds=1))
        )

    def test_draft_and_pending_hidden(self):
        obj = self.draft()
        self.assertFalse(q.can_view(self.reader, obj.pk))
        self.action(obj, "submit")
        self.assertFalse(q.can_view(self.reader, obj.pk))

    def test_equal_window_rejected(self):
        with self.assertRaises(ValidationError):
            self.draft(publish_from=self.now, publish_to=self.now)

    def test_four_eyes(self):
        obj = self.draft()
        self.action(obj, "submit")
        with self.assertRaises(PermissionDenied):
            self.action(obj, "approve")

    def test_reject_revise_resubmit(self):
        obj = self.draft()
        self.action(obj, "submit")
        self.action(obj, "reject", self.root)
        self.action(obj, "revise")
        self.action(obj, "submit")
        self.action(obj, "approve", self.root)
        self.assertTrue(q.can_view(self.reader, obj.pk))

    def test_archived_always_hidden(self):
        obj = self.approved()
        self.action(obj, "archive")
        self.assertFalse(q.can_view(self.reader, obj.pk))
        with self.assertRaises(s.Conflict):
            self.action(obj, "submit")

    def test_stale_write(self):
        obj = self.draft()
        token = q.version(obj)
        self.action(obj, "submit")
        with self.assertRaises(s.Conflict):
            s.workflow(
                actor=self.root,
                pk=obj.pk,
                action="approve",
                expected_version=token,
                reason="review",
            )

    def test_approved_edit_rejected(self):
        obj = self.approved()
        with self.assertRaises(s.Conflict):
            s.write(
                actor=self.author,
                pk=obj.pk,
                expected_version=q.version(obj),
                title="changed",
            )

    def test_inactive_type_denies_approval(self):
        obj = self.draft()
        self.action(obj, "submit")
        s.write_type(
            actor=self.root,
            pk=self.kind.pk,
            type_code="NOTICE",
            type_name="Notice",
            is_active=False,
        )
        with self.assertRaises(ValidationError):
            self.action(obj, "approve", self.root)

    def test_inactive_member_loses_feed(self):
        obj = self.approved()
        Membership.objects.filter(user=self.reader).update(is_active=False)
        self.assertFalse(q.can_view(self.reader, obj.pk))

    def test_other_institution_cannot_read(self):
        obj = self.approved()
        other = Institution.objects.create(
            university=self.institution.university,
            institution_code="OTHER",
            institution_name="Other",
        )
        Membership.objects.filter(user=self.reader).update(institution=other)
        self.assertFalse(q.can_view(self.reader, obj.pk))

    def test_custom_members_only(self):
        obj = self.approved(audience_type="CUSTOM", user_ids=[self.reader.pk])
        self.assertTrue(q.can_view(self.reader, obj.pk))
        self.assertFalse(q.can_view(self.author, obj.pk))

    def test_custom_requires_targets(self):
        with self.assertRaises(ValidationError):
            self.draft(audience_type="CUSTOM")

    def test_forged_custom_target(self):
        stranger = get_user_model().objects.create_user(username="stranger")
        with self.assertRaises(ValidationError):
            self.draft(audience_type="CUSTOM", user_ids=[stranger.pk])

    def test_students_and_department(self):
        person = Student.objects.create(
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            student_number="M14",
            first_name="Reader",
            display_name="Reader",
            student_status="ACTIVE",
        )
        AccountLink.objects.create(user=self.reader, student=person)
        for audience in ["STUDENTS", "DEPARTMENT"]:
            obj = self.approved(audience_type=audience)
            self.assertTrue(q.can_view(self.reader, obj.pk))
            self.assertFalse(q.can_view(self.author, obj.pk))
        person.student_status = "SUSPENDED"
        person.save()
        self.assertFalse(q.can_view(self.reader, obj.pk))

    def test_staff_not_inferred_from_permissions(self):
        obj = self.approved(audience_type="STAFF")
        self.assertFalse(q.can_view(self.author, obj.pk))

    def test_programme_requires_active_enrolment(self):
        programme = Programme.objects.create(
            department=self.department,
            programme_code="M14",
            programme_name="Programme",
            programme_level="UG",
            duration_semesters=8,
        )
        obj = self.approved(audience_type="PROGRAMME", programme_ids=[programme.pk])
        self.assertFalse(q.can_view(self.reader, obj.pk))

    def test_targets_wrong_mode_rejected(self):
        with self.assertRaises(ValidationError):
            self.draft(user_ids=[self.reader.pk])

    def test_scope_required_for_wide_audience(self):
        ScopeGrant.objects.filter(membership=self.membership).update(
            role="DEPARTMENT_ADMIN", campus=self.campus, department=self.department
        )
        with self.assertRaises(NotFound):
            self.draft()
        self.assertEqual(
            self.draft(audience_type="DEPARTMENT").audience_type, "DEPARTMENT"
        )

    def test_disabled_module(self):
        with override_settings(COMMUNICATION_ENABLED=False):
            self.assertFalse(q.feed(self.reader).exists())
            with self.assertRaises(PermissionDenied):
                self.draft()

    def test_attachment_private_download_and_detach_preserves_file(self):
        obj = self.draft()
        self.upload(obj)
        link = obj.attachments.get()
        file = files.FileObject.objects.get(pk=link.file_object_id)
        s.attachment(
            actor=self.author,
            pk=obj.pk,
            expected_version=q.version(obj),
            action="detach",
            file_id=file.pk,
        )
        self.assertTrue(files.FileObject.objects.filter(pk=file.pk).exists())
        self.assertTrue(Path(self.tmp.name, file.storage_key).exists())

    def test_attachment_download_feed_and_confidentiality(self):
        obj = self.draft()
        self.upload(obj, "RESTRICTED")
        self.action(obj, "submit")
        self.action(obj, "approve", self.root)
        link = obj.attachments.get()
        client = APIClient()
        client.force_authenticate(self.reader)
        path = f"/api/v1/communication/feed/{obj.pk}/attachments/{link.file_object_id}/download/"
        self.assertEqual(client.get(path).status_code, 404)
        self.reader.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="documents_exit",
                codename="access_restricted_file",
            )
        )
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF-"))

    def test_attachment_rollback_cleans_storage(self):
        obj = self.draft()
        with (
            patch(
                "apps.communication.services.add_link", side_effect=RuntimeError("test")
            ),
            self.assertRaises(RuntimeError),
        ):
            self.upload(obj)
        self.assertEqual(files.FileObject.objects.count(), 0)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_arbitrary_file_cannot_be_attached(self):
        obj = self.draft()
        with self.assertRaises(NotFound):
            s.attachment(
                actor=self.author,
                pk=obj.pk,
                expected_version=q.version(obj),
                action="attach",
                file_id=999,
            )

    def test_approved_attachment_changes_denied(self):
        obj = self.draft()
        self.upload(obj)
        file_id = obj.attachments.get().file_object_id
        self.action(obj, "submit")
        self.action(obj, "approve", self.root)
        with self.assertRaises(s.Conflict):
            s.attachment(
                actor=self.author,
                pk=obj.pk,
                expected_version=q.version(obj),
                action="detach",
                file_id=file_id,
            )

    def test_api_privacy_unknown_fields_and_hidden_ids(self):
        obj = self.draft()
        client = APIClient()
        client.force_authenticate(self.reader)
        self.assertEqual(
            client.get(f"/api/v1/communication/feed/{obj.pk}/").status_code, 404
        )
        self.assertEqual(
            client.get(f"/api/v1/communication/manage/{obj.pk}/").status_code, 404
        )
        self.assertEqual(
            client.post(
                "/api/v1/communication/drafts/create/",
                {"approval_status": "APPROVED"},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/api/v1/communication/drafts/create/", 1, format="json"
            ).status_code,
            400,
        )
        self.action(obj, "submit")
        self.action(obj, "approve", self.root)
        data = client.get(f"/api/v1/communication/feed/{obj.pk}/").data
        self.assertNotIn("user_ids", data)
        self.assertNotIn("version", data)
        self.assertNotIn("storage_key", str(data))

    def test_audit_required_and_rollback(self):
        with (
            patch(
                "apps.communication.services.audit", side_effect=RuntimeError("test")
            ),
            self.assertRaises(RuntimeError),
        ):
            self.draft()
        self.assertEqual(m.Announcement.objects.count(), 0)

    def test_audit_reader_denied(self):
        obj = self.approved()
        client = APIClient()
        client.force_authenticate(self.reader)
        self.assertEqual(
            client.get(f"/api/v1/communication/audit/{obj.pk}/").status_code, 404
        )

    def test_staff_assignment_and_multi_role_identity(self):
        from apps.people_master.models import Employee, EmployeeAssignment

        employee = Employee.objects.create(
            institution=self.institution,
            employment_source=self.source,
            employee_number="M14",
            first_name="Staff",
            display_name="Staff",
            employment_type="REGULAR",
            employment_status="ACTIVE",
            joining_date=self.now.date() - timedelta(days=1),
        )
        AccountLink.objects.create(user=self.reader, employee=employee)
        staff = self.approved(audience_type="STAFF")
        self.assertTrue(q.can_view(self.reader, staff.pk))
        department = self.approved(audience_type="DEPARTMENT")
        self.assertFalse(q.can_view(self.reader, department.pk))
        assignment = EmployeeAssignment.objects.create(
            employee=employee,
            campus=self.campus,
            department=self.department,
            designation=self.designation,
            start_date=self.now.date() - timedelta(days=1),
        )
        self.assertTrue(q.can_view(self.reader, department.pk))
        assignment.end_date = self.now.date() - timedelta(days=1)
        assignment.save()
        self.assertFalse(q.can_view(self.reader, department.pk))
        person = Student.objects.create(
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            student_number="DUAL",
            first_name="Dual",
            display_name="Dual",
            student_status="ACTIVE",
        )
        AccountLink.objects.create(user=self.reader, student=person)
        self.assertTrue(q.can_view(self.reader, department.pk))
        self.assertTrue(q.can_view(self.reader, staff.pk))

    def test_programme_recipient_revoked_on_enrolment_exit(self):
        from apps.academic_calendar.models import AcademicYear, Semester
        from apps.admission_enrolment.models import (
            AdmissionApplicant,
            AdmissionApplication,
            StudentProgrammeEnrolment,
        )
        from apps.curriculum_catalog.models import CurriculumScheme

        programme = Programme.objects.create(
            department=self.department,
            programme_code="P14",
            programme_name="Programme",
            programme_level="UG",
            duration_semesters=8,
        )
        year = AcademicYear.objects.create(
            year_code="2026",
            start_date="2026-01-01",
            end_date="2026-12-31",
            status="ACTIVE",
        )
        semester = Semester.objects.create(semester_number=1, semester_name="First")
        scheme = CurriculumScheme.objects.create(
            programme=programme,
            scheme_code="P14",
            scheme_name="Scheme",
            regulation_year=2026,
            effective_from="2026-01-01",
            status="ACTIVE",
        )
        person = Student.objects.create(
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            student_number="P14",
            first_name="Student",
            display_name="Student",
            student_status="ACTIVE",
        )
        AccountLink.objects.create(user=self.reader, student=person)
        applicant = AdmissionApplicant.objects.create(
            institution=self.institution,
            first_name="Student",
            display_name="Student",
            created_by=self.root,
            updated_by=self.root,
        )
        application = AdmissionApplication.objects.create(
            application_number="P14",
            admission_applicant=applicant,
            admitted_student=person,
            programme=programme,
            academic_year=year,
            application_date="2026-01-01",
            application_status="ADMITTED",
            eligibility_status="ELIGIBLE",
            created_by=self.root,
            updated_by=self.root,
        )
        enrolment = StudentProgrammeEnrolment.objects.create(
            application=application,
            student=person,
            programme=programme,
            curriculum_scheme=scheme,
            admission_academic_year=year,
            admission_semester=semester,
            admission_date="2026-01-01",
            created_by=self.root,
            updated_by=self.root,
        )
        obj = self.approved(audience_type="PROGRAMME", programme_ids=[programme.pk])
        self.assertTrue(q.can_view(self.reader, obj.pk))
        self.assertFalse(q.can_view(self.author, obj.pk))
        enrolment.enrolment_status = "COMPLETED"
        enrolment.save()
        self.assertFalse(q.can_view(self.reader, obj.pk))

    def test_feed_and_management_query_count_is_bounded(self):
        from django.test.utils import CaptureQueriesContext

        from apps.communication.api.views import manage_qs

        for index in range(5):
            self.approved(title="Notice " + str(index))
        with CaptureQueriesContext(connection) as queries:
            list(q.feed(self.reader))
        self.assertLessEqual(len(queries), 4)
        with CaptureQueriesContext(connection) as queries:
            [q.summary(row, True) for row in manage_qs(self.root)]
        self.assertLessEqual(len(queries), 4)

    def test_multipart_attachment_api(self):
        obj = self.draft()
        client = APIClient()
        client.force_authenticate(self.author)
        response = client.post(
            f"/api/v1/communication/drafts/{obj.pk}/upload/",
            {
                "expected_version": q.version(obj),
                "upload": SimpleUploadedFile(
                    "notice.pdf", pdf(), content_type="application/pdf"
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(obj.attachments.count(), 1)

    def test_attachment_duplicate_and_reorder(self):
        obj = self.draft()
        self.upload(obj)
        link = obj.attachments.get()
        with self.assertRaises(ValidationError):
            s.attachment(
                actor=self.author,
                pk=obj.pk,
                expected_version=q.version(obj),
                action="attach",
                file_id=link.file_object_id,
            )
        s.attachment(
            actor=self.author,
            pk=obj.pk,
            expected_version=q.version(obj),
            action="reorder",
            file_id=link.file_object_id,
            display_order=0,
        )
        self.assertEqual(obj.attachments.get().display_order, 0)

    def test_record_limited_grant_fails_closed(self):
        ScopeGrant.objects.filter(membership=self.membership).update(
            record_limits={"students": [1]}
        )
        with self.assertRaises(NotFound):
            self.draft()

    def test_legacy_extension_gate_retains_rows(self):
        from importlib import import_module

        from django.apps import apps

        obj = self.draft()
        with self.assertRaises(RuntimeError):
            import_module(
                "apps.communication.migrations.0002_institution_and_audience_targets"
            ).legacy_gate(apps, None)
        self.assertTrue(m.Announcement.objects.filter(pk=obj.pk).exists())


class RaceTests(Setup, TransactionTestCase):
    def test_graph_rollback_refuses_to_drop_recipient_ownership(self):
        from django.db.migrations.exceptions import IrreversibleError
        from django.db.migrations.executor import MigrationExecutor

        obj = self.draft(audience_type="CUSTOM", user_ids=[self.reader.pk])
        with self.assertRaises(IrreversibleError):
            MigrationExecutor(connection).migrate([("communication", "0001_baseline")])
        self.assertTrue(
            m.Announcement.objects.filter(
                pk=obj.pk, institution=self.institution
            ).exists()
        )
        self.assertTrue(obj.user_targets.filter(user=self.reader).exists())

    def test_competing_approval_rejection(self):
        obj = self.draft()
        self.action(obj, "submit")
        token = q.version(obj)
        actor_id = self.root.pk

        def run(action):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                s.workflow(
                    actor=actor,
                    pk=obj.pk,
                    action=action,
                    expected_version=token,
                    reason="Race test",
                )
                return "ok"
            except s.Conflict:
                return "conflict"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, ["approve", "reject"]))
        self.assertCountEqual(results, ["ok", "conflict"])
