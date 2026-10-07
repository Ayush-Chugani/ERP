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
from apps.professional_contributions import services as s
from apps.professional_contributions.models import (
    StaffProfessionalContribution,
)
from apps.research_proposals.tests import test_module as base_fixture
from apps.staff_activities.models import (
    ActivityAttachment,
    ActivityCommandReceipt,
    StaffActivity,
)
from apps.staff_profile import models as refs


@override_settings(
    PROFESSIONAL_CONTRIBUTIONS_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ContributionTests(TestCase):
    def setUp(self):
        base_fixture.ProposalTests.setUp(self)
        call_command("seed_professional_contributions", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="PROFESSIONAL_CONTRIBUTIONS."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.category = refs.ProfessionalContributionType.objects.create(
            contribution_code="TEST", contribution_name="Synthetic category"
        )
        self.values = {
            "title_topic": "Synthetic award",
            "professional_contribution_type_id": self.category.pk,
            "contribution_date": date(2026, 1, 1),
        }
        self.url = "/api/v1/professional-contributions/activities/"

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
        self.assertEqual(StaffProfessionalContribution.objects.count(), 1)
        self.assertEqual(
            row.staff_activity.activity_type.activity_type_code, s.TYPE_CODE
        )
        with self.assertRaises(s.Conflict):
            self.create(title_topic="changed")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)

    def test_update_version_and_protected_context(self):
        row = self.create()
        token = s.version(row.pk)
        s.save_activity(
            self.root,
            {"title_topic": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"title_topic": "stale"},
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
                {"title_topic": "No"},
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
            {"title_topic": "Corrected"},
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
        self.assertTrue(StaffProfessionalContribution.objects.filter(pk=pk).exists())

    def test_scope_deny_self_and_export(self):
        row = self.create(title_topic="=HYPERLINK(1)")
        response = self.client.get(self.url + "export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=HYPERLINK", b"".join(response.streaming_content).decode())
        self.grant.scope_type = "DEPARTMENT"
        from apps.organization.models import Department

        self.grant.department = Department.objects.create(
            campus=self.campus, department_code="OTHER24", department_name="Other"
        )
        self.grant.save()
        with self.assertRaises(PermissionDenied):
            self.create(key="cross-scope-create")
        self.assertEqual(StaffProfessionalContribution.objects.count(), 1)
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
            permission_code="PROFESSIONAL_CONTRIBUTIONS.ACTIVITY.READ"
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
        call_command("seed_professional_contributions", stdout=StringIO())
        call_command("seed_professional_contributions", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        refs.ApprovalStatus.objects.filter(status_code="DRAFT").update(is_active=False)
        with self.assertRaises(ValidationError):
            self.create()
        with override_settings(PROFESSIONAL_CONTRIBUTIONS_ENABLED=False):
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
                    "apps.professional_contributions.services.ActivityAttachment.objects.create",
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
            {"title_topic": "Changed"},
            activity_id=row.pk,
            expected_version=original,
        )
        s.save_activity(
            self.root,
            {"title_topic": self.values["title_topic"]},
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
                "apps.professional_contributions.services.record",
                side_effect=RuntimeError("synthetic"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(StaffProfessionalContribution.objects.count(), 0)
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
                    "activity": {"title_topic": "stale"},
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
                {"title_topic": "Should not save"},
                expected_version=s.version(row.pk),
            )
        row.refresh_from_db()
        self.assertEqual(row.title_topic, self.values["title_topic"])

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
                self.values | {"contribution_date": date(1900, 1, 1)},
                context=bad,
                key="old",
            )
        self.assertFalse(StaffProfessionalContribution.objects.exists())

    def test_optional_fields_counts_and_date_boundaries(self):
        minimal = s.save_activity(
            self.root,
            {"professional_contribution_type_id": self.category.pk},
            context=self.context,
            key="minimal",
        )
        self.assertIsNone(minimal.contribution_date)
        self.assertEqual(
            minimal.staff_activity.activity_title, self.category.contribution_name
        )
        for i, values in enumerate(
            [
                {"number_of_reviews": 0, "number_of_candidates": 65535},
                {"start_date": date(2026, 2, 1)},
                {"end_date": date(1900, 1, 1)},
                {"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 1)},
                {"contribution_date": date(2100, 1, 1)},
            ]
        ):
            with self.subTest(values=values):
                self.create(key=f"valid-{i}", **values)
        for i, values in enumerate(
            [
                {"number_of_reviews": -1},
                {"number_of_candidates": 65536},
                {"number_of_reviews": 1.5},
                {"number_of_reviews": True},
                {"start_date": date(2026, 2, 1), "end_date": date(2026, 1, 1)},
                {"contribution_details": chr(0x1F600) * 16384},
            ]
        ):
            before = StaffActivity.objects.count()
            with self.subTest(values=list(values)), self.assertRaises(ValidationError):
                self.create(key=f"invalid-{i}", **values)
            self.assertEqual(StaffActivity.objects.count(), before)
        exact = self.create(key="text-limit", contribution_details="a" * 65535)
        self.assertEqual(len(exact.contribution_details), 65535)

    def contexts(self):
        from apps.conferences.models import ConferenceEvent
        from apps.curriculum_catalog.models import CourseCatalog, CourseCategory
        from apps.organization.models import Programme
        from apps.people_master.models import Student
        from apps.research_publications.models import Journal

        programme = Programme.objects.create(
            department=self.department,
            programme_code="M32",
            programme_name="M32 programme",
            programme_level="UG",
            duration_semesters=8,
        )
        category = CourseCategory.objects.create(
            category_code="M32", category_name="M32 course category"
        )
        course = CourseCatalog.objects.create(
            owning_department=self.department,
            course_category=category,
            course_code="M32",
            course_title="M32 course",
            course_type="THEORY",
        )
        kind = refs.JournalType.objects.create(
            journal_type_code="M32", journal_type_name="M32 journal type"
        )
        journal = Journal.objects.create(journal_name="M32 journal", journal_type=kind)
        event = ConferenceEvent.objects.create(
            conference_title="M32 conference",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )
        student = Student.objects.create(
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            student_number="M32",
            first_name="Synthetic",
            display_name="M32 student",
            student_status="ACTIVE",
        )
        return {
            "organization_id": self.organization.pk,
            "journal_id": journal.pk,
            "conference_event_id": event.pk,
            "programme_id": programme.pk,
            "course_id": course.pk,
            "student_id": student.pk,
        }

    @override_settings(PEOPLE_MASTER_ENABLED=True)
    def test_all_six_contexts_and_lookup_security(self):
        values = self.contexts()
        row = self.create(**values)
        result = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(len(result.data["context_summary"]), 6)
        for endpoint in (
            "organizations",
            "journals",
            "conferences",
            "programmes",
            "courses",
            "students",
        ):
            with self.subTest(endpoint=endpoint):
                url = "/api/v1/professional-contributions/lookups/" + endpoint + "/"
                self.assertEqual(self.client.get(url).data["count"], 0)
                response = self.client.get(url, {"search": "M32"})
                self.assertEqual(response.status_code, 200)
                for item in response.data["results"]:
                    self.assertEqual(set(item), {"id", "label"})
        # M32 approval/creation alone cannot grant access to students.
        other = self.reviewer()
        with self.assertRaises(ValidationError):
            s.save_activity(
                other,
                self.values | values,
                context=self.context,
                key="no-student-access",
            )
        from apps.organization.models import Institution
        from apps.people_master.models import Student

        institution = Institution.objects.create(
            university=self.institution.university,
            institution_code="M32OTHER",
            institution_name="Other",
        )
        Student.objects.filter(pk=values["student_id"]).update(institution=institution)
        with self.assertRaises(ValidationError):
            self.create(key="foreign-student", **values)

    @override_settings(PEOPLE_MASTER_ENABLED=True)
    def test_type_policy_forms_and_repeated_assignments(self):
        from apps.professional_contributions.forms import ContributionForm
        from apps.professional_contributions.selectors import duplicate_candidates

        values = self.contexts()
        with override_settings(
            PROFESSIONAL_CONTRIBUTIONS_TYPE_RULES={
                "TEST": ["journal_id", "number_of_reviews"]
            }
        ):
            with self.assertRaises(ValidationError):
                self.create()
            row = self.create(**values, number_of_reviews=0)
            form = ContributionForm(
                data={"professional_contribution_type": self.category.pk},
                actor=self.root,
                parent=row.staff_activity,
            )
            self.assertFalse(form.is_valid())
            self.assertIn("number_of_reviews", form.errors)
            self.assertEqual(
                self.client.get(
                    "/api/v1/professional-contributions/lookups/types/"
                ).data["results"][0]["required_fields"],
                ["journal_id", "number_of_reviews"],
            )
        again = self.create(key="repeat", **values, number_of_reviews=0)
        self.assertEqual(duplicate_candidates(self.root, again), [row.pk])
        self.assertEqual(StaffProfessionalContribution.objects.count(), 2)
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            self.create(key="inactive")

    def test_counts_api_filters_aggregates_and_query_bound(self):
        for value in (-1, 65536, 1.5, True, "1.1"):
            response = self.client.post(
                self.url,
                {
                    "context": self.context,
                    "activity": self.values | {"number_of_reviews": value},
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="invalid",
            )
            self.assertEqual(response.status_code, 400, response.data)
        first = self.create(number_of_reviews=65535, number_of_candidates=0)
        query_counts = []
        for size in (1, 8):
            for i in range(1, size):
                self.create(key=f"query-{i}")
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            query_counts.append(len(captured))
        self.assertEqual(query_counts[0], query_counts[1])
        response = self.client.get(self.url + "summary/")
        self.assertEqual(response.data["recorded_counts"]["reviews"], 65535)
        self.assertEqual(response.data["recorded_counts"]["candidates"], 0)
        self.assertEqual(response.data["recorded_counts"]["reviews_recorded"], 1)
        self.assertEqual(
            self.client.get(
                self.url, {"type": self.category.pk, "search": "Synthetic"}
            ).data["count"],
            8,
        )
        self.assertEqual(
            self.client.get(self.url, {"date_from": "2027-01-01"}).data["count"], 0
        )
        response = self.client.put(
            self.url + str(first.pk) + "/",
            {
                "activity": {"professional_contribution_type_id": self.category.pk},
                "version": s.version(first.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["number_of_reviews"])
        self.assertIsNone(response.data["title_topic"])
        exported = self.client.get(self.url + "export/")
        self.assertEqual(exported.status_code, 200)
        self.assertIn(
            "number_of_reviews", b"".join(exported.streaming_content).decode()
        )
        self.assertEqual(
            self.client.get(self.url + str(first.pk) + "/audit_history/").status_code,
            200,
        )

    def test_native_constraints_history_guard_and_schema(self):
        from importlib import import_module

        from django.db import DatabaseError

        row = self.create()
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM staff_professional_contribution")
            columns = {r[0]: r for r in cursor.fetchall()}
            self.assertEqual(len(columns), 17)
            self.assertEqual(columns["number_of_reviews"][1], "smallint unsigned")
        for sql in [
            "UPDATE staff_professional_contribution SET number_of_reviews=-1",
            "UPDATE staff_professional_contribution SET start_date='2026-02-01',end_date='2026-01-01'",
            "DELETE FROM platform_professional_contributions_status_history",
        ]:
            with (
                self.assertRaises(DatabaseError),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(sql)
        from django.apps import apps

        with self.assertRaises(RuntimeError):
            import_module(
                "apps.professional_contributions.migrations.0001_initial"
            ).guard_reverse(apps, None)
        with self.assertNumQueries(0):
            self.assertEqual(str(row), row.title_topic)

    def test_master_admin_and_governed_type_api(self):
        from django.contrib.admin import AdminSite
        from django.test import RequestFactory

        from apps.professional_contributions.admin import (
            StaffProfessionalContributionAdmin,
        )

        row = self.create()
        admin = StaffProfessionalContributionAdmin(
            StaffProfessionalContribution, AdminSite()
        )
        request = RequestFactory().get("/")
        request.user = self.root
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request, row))
        self.assertTrue(admin.has_view_permission(request, row))
        url = "/api/v1/professional-contributions/type-admin/"
        response = self.client.post(
            url,
            {
                "contribution_code": "EXAMPLE",
                "contribution_name": "Example",
                "description": "Optional guidance",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            self.client.patch(url + "bad/", {}, format="json").status_code, 404
        )
        self.assertEqual(
            self.client.delete(url + response.data["id"] + "/").status_code, 405
        )

    def test_duplicate_preview_is_read_only_scoped_and_correlated(self):
        row = self.create(
            title_topic="Repeated topic", appointment_reference_number="ABC 123"
        )
        counts = (
            StaffActivity.objects.count(),
            ActivityCommandReceipt.objects.count(),
            iam.ActivityAudit.objects.count(),
        )
        with self.assertLogs("sims.professional_contributions", level="INFO") as logs:
            response = self.client.post(
                self.url + "duplicate-preview/",
                {
                    "context": self.context,
                    "activity": self.values
                    | {
                        "title_topic": " Repeated   topic ",
                        "appointment_reference_number": "ABC  123",
                    },
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["candidates"], [str(row.pk)])
        self.assertEqual(
            counts,
            (
                StaffActivity.objects.count(),
                ActivityCommandReceipt.objects.count(),
                iam.ActivityAudit.objects.count(),
            ),
        )
        self.assertTrue(response["X-Request-ID"])
        self.assertNotIn("Repeated", str(logs.output))
        self.grant.delete()
        response = self.client.post(
            self.url + "duplicate-preview/",
            {"context": self.context, "activity": self.values},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_api_audit_correlates_and_policy_patch_uses_complete_record(self):
        response = self.client.post(
            self.url,
            {
                "context": self.context,
                "activity": self.values | {"number_of_reviews": 0},
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="correlated",
        )
        self.assertEqual(response.status_code, 201, response.data)
        row = StaffProfessionalContribution.objects.get(
            pk=response.data["staff_activity"]
        )
        audit = iam.ActivityAudit.objects.filter(
            module_code=s.MODULE, entity_id=str(row.pk)
        ).latest("pk")
        self.assertEqual(audit.request_identifier, response["X-Request-ID"])
        with override_settings(
            PROFESSIONAL_CONTRIBUTIONS_TYPE_RULES={"TEST": ["number_of_reviews"]}
        ):
            response = self.client.patch(
                self.url + str(row.pk) + "/",
                {
                    "activity": {"professional_contribution_type_id": self.category.pk},
                    "version": s.version(row.pk),
                },
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
            response = self.client.patch(
                self.url + str(row.pk) + "/",
                {"activity": {"number_of_reviews": None}, "version": s.version(row.pk)},
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)

    @override_settings(PEOPLE_MASTER_ENABLED=True)
    def test_inactive_contexts_foreign_academics_and_scoped_student_reads(self):
        from apps.organization.models import Campus, Department, Institution
        from apps.professional_contributions.selectors import REFERENCES

        values = self.contexts()
        row = self.create(**values)
        for name, (model, _) in REFERENCES.items():
            if name == "student":
                continue
            pk = values[name + "_id"]
            model.objects.filter(pk=pk).update(is_active=False)
            with self.subTest(reference=name), self.assertRaises(ValidationError):
                self.create(key="inactive-" + name, **values)
            model.objects.filter(pk=pk).update(is_active=True)
        other = Institution.objects.create(
            university=self.institution.university,
            institution_code="FOREIGN",
            institution_name="Foreign",
        )
        campus = Campus.objects.create(
            institution=other, campus_code="FOREIGN", campus_name="Foreign"
        )
        department = Department.objects.create(
            campus=campus, department_code="FOREIGN", department_name="Foreign"
        )
        for name, field in (
            ("programme", "department"),
            ("course", "owning_department"),
        ):
            model = REFERENCES[name][0]
            model.objects.filter(pk=values[name + "_id"]).update(**{field: department})
            with self.subTest(reference=name), self.assertRaises(ValidationError):
                self.create(key="foreign-" + name, **values)
            model.objects.filter(pk=values[name + "_id"]).update(
                **{field: self.department}
            )
        with override_settings(PEOPLE_MASTER_ENABLED=False):
            from django.contrib.admin import AdminSite
            from django.test import RequestFactory

            from apps.professional_contributions.admin import (
                StaffProfessionalContributionAdmin,
            )

            request = RequestFactory().get("/")
            request.user = self.root
            admin = StaffProfessionalContributionAdmin(
                StaffProfessionalContribution, AdminSite()
            )
            self.assertFalse(admin.has_view_permission(request, row))
            self.assertEqual(self.client.get(self.url).data["count"], 0)
            self.assertEqual(
                self.client.get(self.url + str(row.pk) + "/").status_code, 404
            )
            with self.assertRaises(NotFound):
                s.update_activity(
                    self.root,
                    row.pk,
                    {"title_topic": "Hidden"},
                    expected_version=s.version(row.pk),
                )
        with CaptureQueriesContext(connection) as first:
            self.client.get(self.url)
        self.create(key="all-contexts-repeat", **values)
        with CaptureQueriesContext(connection) as second:
            self.client.get(self.url)
        self.assertEqual(len(first), len(second))
