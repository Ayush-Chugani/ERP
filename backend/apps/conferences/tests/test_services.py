from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.conferences import models as m
from apps.conferences import services as s
from apps.conferences.permissions import activity_scope
from apps.conferences.validators import doi
from apps.identity_access import models as iam
from apps.people_master.models import AccountLink, EmployeeAssignment
from apps.research_publications.tests import test_models as publication_tests
from apps.staff_activities.models import StaffActivity
from apps.staff_profile import models as refs


@override_settings(
    CONFERENCES_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ConferenceTests(TestCase):
    def setUp(self):
        publication_tests.PublicationModelTests.setUp(self)
        from apps.identity_access.seeding import catalogue

        for index, values in enumerate(catalogue()["actions"], start=1):
            iam.AccessAction.objects.get_or_create(
                action_code=values["action_code"], defaults={"pk": index, **values}
            )
        self.kind.activity_group = "CONFERENCE"
        self.kind.save()
        self.verification.status_code = "PENDING"
        self.verification.save()
        self.approval.status_code = "PENDING"
        self.approval.save()
        self.assignment = EmployeeAssignment.objects.create(
            employee=self.employee,
            campus=self.campus,
            department=self.department,
            designation=self.designation,
            start_date=date(2020, 1, 1),
        )
        self.contribution = refs.ConferenceContributionType.objects.create(
            type_code="SYNTHETIC", type_name="Synthetic"
        )
        self.agency = refs.IndexingAgency.objects.create(
            agency_code="SYNTHETIC", agency_name="Synthetic"
        )
        module = iam.AccessModule.objects.create(
            module_code="CONFERENCES", module_name="Conferences"
        )
        self.role = iam.Role.objects.create(
            role_code="SYNTHETIC_M22",
            role_name="Synthetic M22",
            role_category="SYSTEM",
            role_level="GLOBAL",
        )
        for code in ("EVENT", "ACTIVITY"):
            resource = iam.AccessResource.objects.create(
                access_module=module, resource_code=code, resource_name=code
            )
            for action in ("READ", "CREATE", "UPDATE", "DELETE", "VERIFY", "EXPORT"):
                verb = iam.AccessAction.objects.get(action_code=action)
                perm = iam.Permission.objects.create(
                    access_resource=resource,
                    access_action=verb,
                    permission_code=f"CONFERENCES.{code}.{action}",
                    permission_name=f"{code} {action}",
                )
                iam.RolePermission.objects.create(role=self.role, permission=perm)
        self.grant = iam.UserRoleAssignment.objects.create(
            user=self.root,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.event = s.save_event(
            self.root,
            {
                "conference_title": "Synthetic event",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 1, 2),
            },
        )
        self.context = {
            "employee_id": self.employee.pk,
            "employee_assignment_id": self.assignment.pk,
            "activity_type_id": self.kind.pk,
        }

    def create(self, **values):
        data = {
            "conference_event_id": self.event.pk,
            "conference_contribution_type_id": self.contribution.pk,
            "paper_title": "Synthetic paper",
        }
        data.update(values)
        return s.save_activity(self.root, data, context=self.context)

    def test_atomic_create_identity_and_doi(self):
        row = self.create(doi="https://doi.org/10.1234/SYNTHETIC")
        self.assertEqual(row.pk, row.staff_activity.pk)
        self.assertEqual(row.doi, "10.1234/synthetic")
        self.assertEqual(row.staff_activity.activity_title, "Synthetic paper")
        count = StaffActivity.objects.count()
        with self.assertRaises(s.Conflict):
            self.create(doi="doi:10.1234/synthetic")
        self.assertEqual(StaffActivity.objects.count(), count)

    def test_dates_and_metadata_validation(self):
        with self.assertRaises(ValidationError):
            s.save_event(
                self.root,
                {
                    "conference_title": "Invalid",
                    "start_date": date(2026, 2, 1),
                    "end_date": date(2026, 1, 1),
                },
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.ConferenceEvent.objects.create(
                conference_title="Invalid",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 1, 1),
            )
        for values in [
            {"page_from": "20", "page_to": "10"},
            {"proceedings_url": "javascript:alert(1)"},
            {"award_date": date(2026, 1, 1)},
            {"issn": "invalid"},
        ]:
            with self.assertRaises(ValidationError):
                self.create(**values)
        self.assertEqual(doi(" DOI:10.1234/Test "), "10.1234/test")

    def test_stale_edit_and_protected_ownership(self):
        row = self.create()
        token = s.version(row.pk)
        s.save_activity(
            self.root,
            {"paper_title": "Revised"},
            activity_id=row.pk,
            expected_version=token,
        )
        with self.assertRaises(s.Conflict):
            s.save_activity(
                self.root,
                {"paper_title": "Stale"},
                activity_id=row.pk,
                expected_version=token,
            )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {"staff_activity_id": 9},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
            )

    def test_scope_deny_precedence_on_read_and_write(self):
        row = self.create()
        perm = iam.Permission.objects.get(permission_code="CONFERENCES.ACTIVITY.READ")
        iam.UserPermissionOverride.objects.create(
            user=self.root,
            permission=perm,
            scope_type="INSTITUTION",
            scope_entity_id=self.institution.pk,
            permission_effect="DENY",
            valid_from=timezone.now() - timedelta(days=1),
            justification="Synthetic test",
        )
        self.assertFalse(
            m.ConferenceActivity.objects.filter(activity_scope(self.root)).exists()
        )
        self.grant.assignment_status = "REVOKED"
        self.grant.save()
        with self.assertRaises(PermissionDenied):
            s.save_activity(
                self.root,
                {"paper_title": "Unauthorized"},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
            )

    def test_index_claims_verification_and_self_verification_denial(self):
        row = self.create()
        claim = {
            "indexing_agency_id": self.agency.pk,
            "source_url": "https://example.org/evidence",
            "remarks": "Synthetic",
        }
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
                indexing=[claim, claim],
            )
        s.save_activity(
            self.root,
            {},
            activity_id=row.pk,
            expected_version=s.version(row.pk),
            indexing=[claim],
        )
        indexing = m.ConferenceActivityIndexing.objects.get(pk=(row.pk, self.agency.pk))
        self.assertEqual(indexing.indexing_status, "CLAIMED")
        AccountLink.objects.create(user=self.root, employee=self.employee)
        with self.assertRaises(PermissionDenied):
            s.verify_indexing(
                self.root,
                row.pk,
                self.agency.pk,
                "VERIFIED",
                "https://example.org/evidence",
                "Synthetic",
            )
        verifier = type(self.root).objects.create_user(username="synthetic-verifier")
        iam.UserRoleAssignment.objects.create(
            user=verifier,
            role=self.role,
            scope_type="GLOBAL",
            valid_from=timezone.now() - timedelta(days=1),
        )
        s.verify_indexing(
            verifier,
            row.pk,
            self.agency.pk,
            "VERIFIED",
            "https://example.org/evidence",
            "Synthetic",
            expected_version=s.version(row.pk),
        )
        with self.assertRaises(ValidationError):
            s.save_activity(
                self.root,
                {},
                activity_id=row.pk,
                expected_version=s.version(row.pk),
                indexing=[],
            )

    def test_archive_and_audit(self):
        row = self.create()
        s.archive_activity(self.root, row.pk, s.version(row.pk))
        row.staff_activity.refresh_from_db()
        self.assertIsNotNone(row.staff_activity.deleted_at)
        self.assertTrue(
            iam.ActivityAudit.objects.filter(
                module_code="CONFERENCES", action_code="DELETE"
            ).exists()
        )
