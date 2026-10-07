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

from apps.cocurricular import services as s
from apps.cocurricular.models import (
    CocurricularActivity,
    CocurricularStatusHistory,
)
from apps.common_reference.models import Country, State
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
    COCURRICULAR_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class CocurricularTests(TestCase):
    def setUp(self):
        base_fixture.ProposalTests.setUp(self)
        call_command("seed_cocurricular", stdout=StringIO())
        for permission in iam.Permission.objects.filter(
            permission_code__startswith="COCURRICULAR."
        ):
            iam.RolePermission.objects.create(role=self.role, permission=permission)
        self.category = refs.CoCurricularCategory.objects.create(
            category_code="TEST", category_name="Synthetic category"
        )
        self.country = Country.objects.create(
            iso_code="ZZ", country_name="Synthetic country"
        )
        self.state = State.objects.create(
            country=self.country, state_code="ZZ", state_name="Synthetic state"
        )
        self.values = {
            "event_name": "Synthetic event",
            "cocurricular_category_id": self.category.pk,
            "event_date": date(2026, 1, 1),
            "country_id": self.country.pk,
            "state_id": self.state.pk,
        }
        self.url = "/api/v1/cocurricular/activities/"

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
        self.assertEqual(CocurricularActivity.objects.count(), 1)
        self.assertEqual(
            row.staff_activity.activity_type.activity_type_code, s.TYPE_CODE
        )
        with self.assertRaises(s.Conflict):
            self.create(event_name="changed")
        self.grant.delete()
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertEqual(ActivityCommandReceipt.objects.count(), 1)

    def test_update_version_and_protected_context(self):
        row = self.create()
        token = s.version(row.pk)
        s.save_activity(
            self.root,
            {"event_name": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"event_name": "stale"},
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
                {"event_name": "No"},
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
            {"event_name": "Corrected"},
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
        self.assertTrue(CocurricularActivity.objects.filter(pk=pk).exists())

    def test_scope_deny_self_and_export(self):
        row = self.create(event_name="=HYPERLINK(1)")
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
        self.assertEqual(CocurricularActivity.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url + str(row.pk) + "/").status_code, 404)
        self.grant.scope_type = "SELF"
        self.grant.department = None
        self.grant.save()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        AccountLink.objects.create(user=self.root, employee=self.employee)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        perm = iam.Permission.objects.get(permission_code="COCURRICULAR.ACTIVITY.READ")
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
        call_command("seed_cocurricular", stdout=StringIO())
        call_command("seed_cocurricular", stdout=StringIO())
        self.assertEqual(iam.UserRoleAssignment.objects.count(), count)
        refs.ApprovalStatus.objects.filter(status_code="DRAFT").update(is_active=False)
        with self.assertRaises(ValidationError):
            self.create()
        with override_settings(COCURRICULAR_ENABLED=False):
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
                    "apps.cocurricular.services.ActivityAttachment.objects.create",
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
            {"event_name": "Changed"},
            activity_id=row.pk,
            expected_version=original,
        )
        s.save_activity(
            self.root,
            {"event_name": self.values["event_name"]},
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
                "apps.cocurricular.services.record",
                side_effect=RuntimeError("synthetic"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.create()
        self.assertEqual(StaffActivity.objects.count(), before)
        self.assertEqual(CocurricularActivity.objects.count(), 0)
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
                    "activity": {"event_name": "stale"},
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
                    "category": "BROCHURE",
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
                {"event_name": "Should not save"},
                expected_version=s.version(row.pk),
            )
        row.refresh_from_db()
        self.assertEqual(row.event_name, self.values["event_name"])

    def test_geography_dates_optional_fields_and_native_text(self):
        for values in [
            {"event_name": " "},
            {"state_id": self.state.pk, "country_id": None},
            {"event_date": date(2026, 1, 2)},
            {"cocurricular_category_id": 999999},
            {"staff_activity_id": 999},
            {"contribution_details": chr(0x1F600) * 16384},
        ]:
            with self.subTest(values=list(values)):
                with self.assertRaises((ValidationError, NotFound)):
                    self.create(**values)
                self.assertEqual(StaffActivity.objects.count(), 0)
        row = self.create(event_date=None, country_id=None, state_id=None)
        self.assertIsNone(row.event_date)
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            self.create(key="inactive")
        response = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(response.data["category_name"], self.category.category_name)

    def test_country_state_lookup_and_master_permissions(self):
        self.create()
        path = "/api/v1/cocurricular/lookups/"
        for resource in (
            "categories",
            "organizers",
            "organizations",
            "countries",
            "statuses",
            "years",
            "assignments",
        ):
            self.assertEqual(self.client.get(path + resource + "/").status_code, 200)
        self.assertEqual(self.client.get(path + "states/").status_code, 400)
        response = self.client.get(path + "states/", {"country": self.country.pk})
        self.assertEqual(response.data["results"][0]["label"], self.state.state_name)
        admin = "/api/v1/cocurricular/category-admin/"
        response = self.client.post(
            admin,
            {"category_code": "NEW", "category_name": "New category"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="COCURRICULAR.MASTER.UPDATE"
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
            self.create(key=f"more-{i}", city="Other")
        with CaptureQueriesContext(connection) as later:
            self.client.get(self.url)
        self.assertEqual(len(first), len(later))
        self.assertEqual(self.client.get(self.url, {"city": "Other"}).data["count"], 4)
        self.assertEqual(
            self.client.get(self.url, {"date_from": "invalid"}).status_code, 400
        )
        self.assertEqual(
            self.client.get(self.url, {"ordering": "password"}).status_code, 400
        )
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 5)
        iam.RolePermission.objects.filter(
            role=self.role, permission__permission_code="COCURRICULAR.ACTIVITY.EXPORT"
        ).delete()
        self.assertEqual(self.client.get(self.url + "summary/").data["count"], 0)
        self.assertEqual(self.client.get(self.url).data["count"], 5)

    def test_native_schema_history_and_rollback_guard(self):
        from importlib import import_module

        from django.apps import apps
        from django.db import DatabaseError

        row = self.create()
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE cocurricular_activity")
            ddl = cursor.fetchone()[1].lower()
            for fragment in [
                "bigint unsigned",
                "smallint unsigned",
                "fk_cocurricular_activity_category",
                "varchar(500)",
                "utf8mb4_unicode_ci",
            ]:
                self.assertIn(fragment, ddl)
        with (
            self.assertRaises(DatabaseError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE platform_cocurricular_status_history SET remarks='tamper'"
            )
        with (
            self.assertRaises(RuntimeError),
            connection.schema_editor(atomic=False) as editor,
        ):
            import_module(
                "apps.cocurricular.migrations.0002_retain_status_history"
            ).reverse(apps, editor)
        self.assertEqual(
            CocurricularStatusHistory.objects.get(activity=row).remarks, "Draft created"
        )

    @override_settings(COCURRICULAR_EVENT_HANDLER="synthetic.adapter")
    def test_events_commit_retry_and_rollback(self):
        row = self.create()
        token = s.version(row.pk)
        with (
            patch("apps.cocurricular.events.import_string") as load,
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
            patch("apps.cocurricular.events.import_string") as load,
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
            CocurricularStatusHistory.objects.filter(activity=row).count(), 2
        )

    def test_all_source_fields_and_cross_country_integrity(self):
        organizer = refs.Organizer.objects.create(organization=self.organization)
        other_country = Country.objects.create(
            iso_code="ZX", country_name="Other synthetic country"
        )
        with self.assertRaises(ValidationError):
            self.create(country_id=other_country.pk)
        row = self.create(
            organizer_id=organizer.pk,
            institution_organization_id=self.organization.pk,
            venue_name="Main hall",
            city="Pune",
            achievement_award="Recognition",
            contribution_details="Faculty coordination",
        )
        response = self.client.get(self.url + str(row.pk) + "/")
        self.assertEqual(response.status_code, 200, response.data)
        for name, value in {
            "organizer_name": self.organization.organization_name,
            "institution_organization_name": self.organization.organization_name,
            "venue_name": "Main hall",
            "city": "Pune",
            "achievement_award": "Recognition",
            "contribution_details": "Faculty coordination",
            "country_name": self.country.country_name,
            "state_name": self.state.state_name,
        }.items():
            self.assertEqual(response.data[name], value)
        self.organization.is_active = False
        self.organization.save()
        with self.assertRaises(ValidationError):
            s.update_activity(
                self.root,
                row.pk,
                {"event_name": "New"},
                expected_version=s.version(row.pk),
            )
        self.assertEqual(
            self.client.get(self.url + str(row.pk) + "/").data["organizer_name"],
            self.organization.organization_name,
        )
