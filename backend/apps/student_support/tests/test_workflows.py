from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError as ModelError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.test import APIClient

from apps.core.models import ReferenceAuditEvent
from apps.organization.models import Department
from apps.people_master import models as people
from apps.people_master.tests.test_services import fixture
from apps.student_support import models as m
from apps.student_support import permissions as p
from apps.student_support import selectors as q
from apps.student_support import services as s
from apps.tenancy.models import Membership, ScopeGrant


@override_settings(STUDENT_SUPPORT_ENABLED=True)
class SupportTests(TestCase):
    def setUp(self):
        fixture(self)
        self.setting = override_settings(
            STUDENT_SUPPORT_INSTITUTIONS=[self.institution.pk]
        )
        self.setting.enable()
        self.addCleanup(self.setting.disable)
        self.student = people.Student.objects.create(
            institution=self.institution,
            campus=self.campus,
            department=self.department,
            student_number="M12",
            first_name="Student",
            display_name="Student",
            student_status="ACTIVE",
        )
        self.employee = people.Employee.objects.create(
            institution=self.institution,
            employment_source=self.source,
            employee_number="M12",
            first_name="Mentor",
            display_name="Mentor",
            employment_type="REGULAR",
            employment_status="ACTIVE",
            joining_date=timezone.localdate(),
        )
        self.user = self.actor(
            "student",
            ["submit_own_grievance", "view_own_grievance", "view_counselling_normal"],
        )
        people.AccountLink.objects.create(user=self.user, student=self.student)
        self.mentor = self.actor(
            "mentor",
            [
                "conduct_counselling",
                "view_counselling_normal",
                "view_counselling_restricted",
            ],
        )
        people.AccountLink.objects.create(user=self.mentor, employee=self.employee)
        self.category = s.category_write(
            actor=self.root, category_code="TEST", category_name="Test only"
        )
        self.assignment = s.assign_mentor(
            actor=self.root,
            student_id=self.student.pk,
            employee_id=self.employee.pk,
            start_date=timezone.localdate() - timedelta(days=10),
        )

    def actor(self, name, caps, department=None):
        user = get_user_model().objects.create_user(username=name)
        user.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label="student_support", codename__in=caps
            )
        )
        member = Membership.objects.create(user=user, institution=self.institution)
        if department:
            ScopeGrant.objects.create(
                membership=member,
                role="DEPARTMENT_ADMIN",
                campus=department.campus,
                department=department,
            )
        return user

    def grievance(self):
        return s.submit_grievance(
            actor=self.user,
            grievance_category_id=self.category.pk,
            subject="Private subject",
            description="SECRET DESCRIPTION",
            department_id=self.department.pk,
        )

    def session(self, level="RESTRICTED"):
        return s.schedule_session(
            actor=self.mentor,
            mentor_assignment_id=self.assignment.pk,
            session_date=timezone.now() - timedelta(hours=1),
            confidentiality_level=level,
        )

    def test_schema_fidelity(self):
        from apps.student_support.migrations._canonical import DDL, verify

        with connection.cursor() as cursor:
            for sql in DDL:
                self.assertTrue(verify(cursor, sql))
        self.assertNotIn("actor", [f.name for f in m.GrievanceAction._meta.fields])
        self.assertEqual(
            m.CounsellingSession._meta.get_field("session_status").default, "COMPLETED"
        )

    def test_overlap_policy_both_modes(self):
        s.assign_mentor(
            actor=self.root,
            student_id=self.student.pk,
            employee_id=self.employee.pk,
            start_date=timezone.localdate(),
        )
        with (
            override_settings(
                STUDENT_SUPPORT_POLICIES={
                    str(self.institution.pk): {"allow_overlapping_mentors": False}
                }
            ),
            self.assertRaises(s.Conflict),
        ):
            s.assign_mentor(
                actor=self.root,
                student_id=self.student.pk,
                employee_id=self.employee.pk,
                start_date=timezone.localdate(),
            )

    def test_reassignment_preserves_history_and_rolls_back(self):
        old = self.assignment
        with (
            patch(
                "apps.student_support.audit.emit",
                side_effect=RuntimeError("audit failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            s.change_mentor(
                actor=self.root,
                pk=old.pk,
                expected_status="ACTIVE",
                employee_id=self.employee.pk,
                start_date=timezone.localdate(),
            )
        old.refresh_from_db()
        self.assertEqual(old.assignment_status, "ACTIVE")
        self.assertEqual(m.MentorAssignment.objects.count(), 1)
        new = s.change_mentor(
            actor=self.root,
            pk=old.pk,
            expected_status="ACTIVE",
            employee_id=self.employee.pk,
            start_date=timezone.localdate(),
        )
        old.refresh_from_db()
        self.assertEqual(old.assignment_status, "COMPLETED")
        self.assertNotEqual(new.pk, old.pk)

    def test_invalid_dates_and_unauthorized_assignment(self):
        with self.assertRaises(ValidationError):
            s.assign_mentor(
                actor=self.root,
                student_id=self.student.pk,
                employee_id=self.employee.pk,
                start_date=timezone.localdate(),
                end_date=timezone.localdate() - timedelta(days=1),
            )
        with self.assertRaises(NotFound):
            s.assign_mentor(
                actor=self.user,
                student_id=self.student.pk,
                employee_id=self.employee.pk,
                start_date=timezone.localdate(),
            )

    def test_counselling_levels_and_idor(self):
        row = self.session()
        s.session_action(
            actor=self.mentor,
            pk=row.pk,
            expected_status="SCHEDULED",
            action="complete",
            observations="SECRET NOTES",
            action_plan="SECRET PLAN",
        )
        self.assertEqual(
            q.session_detail(actor=self.mentor, pk=row.pk)["observations"],
            "SECRET NOTES",
        )
        with self.assertRaises(NotFound):
            q.session_detail(actor=self.user, pk=row.pk)
        unrelated = self.actor(
            "unrelated", ["view_counselling_restricted", "conduct_counselling"]
        )
        with self.assertRaises(NotFound):
            q.session_detail(actor=unrelated, pk=row.pk)
        self.assertNotIn(
            "SECRET", str(list(ReferenceAuditEvent.objects.values("before", "after")))
        )
        self.assertTrue(
            ReferenceAuditEvent.objects.filter(
                actor=self.mentor, after__event="session_read"
            ).exists()
        )

    def test_student_normal_policy_and_confidentiality_change(self):
        row = self.session("NORMAL")
        self.assertEqual(
            q.session_detail(actor=self.user, pk=row.pk)["id"], str(row.pk)
        )
        with (
            override_settings(
                STUDENT_SUPPORT_POLICIES={
                    str(self.institution.pk): {"student_normal_notes": False}
                }
            ),
            self.assertRaises(NotFound),
        ):
            q.session_detail(actor=self.user, pk=row.pk)
        with self.assertRaises(NotFound):
            s.session_action(
                actor=self.mentor,
                pk=row.pk,
                expected_status="SCHEDULED",
                action="confidentiality",
                confidentiality_level="RESTRICTED",
            )
        s.session_action(
            actor=self.root,
            pk=row.pk,
            expected_status="SCHEDULED",
            action="confidentiality",
            confidentiality_level="HIGHLY_RESTRICTED",
        )
        with self.assertRaises(NotFound):
            q.session_detail(actor=self.mentor, pk=row.pk)

    def test_session_followup_date_and_assignment_window(self):
        row = self.session()
        with self.assertRaises(ValidationError):
            s.session_action(
                actor=self.mentor,
                pk=row.pk,
                expected_status="SCHEDULED",
                action="follow-up",
            )
        with self.assertRaises(ValidationError):
            s.schedule_session(
                actor=self.mentor,
                mentor_assignment_id=self.assignment.pk,
                session_date=timezone.now() - timedelta(days=20),
            )
        done = s.session_action(
            actor=self.mentor,
            pk=row.pk,
            expected_status="SCHEDULED",
            action="follow-up",
            follow_up_date=timezone.localdate() + timedelta(days=1),
        )
        self.assertEqual(done.session_status, "FOLLOW_UP_REQUIRED")

    def test_grievance_state_machine_and_history(self):
        obj = self.grievance()
        with self.assertRaises(s.Conflict):
            s.grievance_action(
                actor=self.root, pk=obj.pk, expected_status="SUBMITTED", action="close"
            )
        s.grievance_action(
            actor=self.root, pk=obj.pk, expected_status="SUBMITTED", action="review"
        )
        with self.assertRaises(ValidationError):
            s.grievance_action(
                actor=self.root,
                pk=obj.pk,
                expected_status="UNDER_REVIEW",
                action="resolve",
            )
        s.grievance_action(
            actor=self.root,
            pk=obj.pk,
            expected_status="UNDER_REVIEW",
            action="resolve",
            resolution="SECRET RESOLUTION",
        )
        closed = s.grievance_action(
            actor=self.root, pk=obj.pk, expected_status="RESOLVED", action="close"
        )
        self.assertEqual(closed.resolution, "SECRET RESOLUTION")
        self.assertIsNotNone(closed.resolved_at)
        self.assertEqual(m.GrievanceAction.objects.filter(grievance=obj).count(), 4)
        with self.assertRaises(s.Conflict):
            s.grievance_action(
                actor=self.root, pk=obj.pk, expected_status="CLOSED", action="review"
            )

    def test_history_and_audit_failures_rollback(self):
        obj = self.grievance()
        for target in [
            "apps.student_support.models.GrievanceAction.objects.create",
            "apps.student_support.audit.emit",
        ]:
            with (
                patch(target, side_effect=RuntimeError("injected")),
                self.assertRaises(RuntimeError),
            ):
                s.grievance_action(
                    actor=self.root,
                    pk=obj.pk,
                    expected_status="SUBMITTED",
                    action="review",
                )
            obj.refresh_from_db()
            self.assertEqual(obj.status, "SUBMITTED")
            self.assertEqual(m.GrievanceAction.objects.filter(grievance=obj).count(), 1)

    def test_department_scope_ownership_and_no_mentor_grievance_access(self):
        obj = self.grievance()
        staff = self.actor("staff", ["triage_grievance"], self.department)
        self.assertEqual(q.grievance_detail(actor=staff, pk=obj.pk)["id"], str(obj.pk))
        other = Department.objects.create(
            campus=self.campus, department_code="OTHER", department_name="Other"
        )
        outsider = self.actor("outsider", ["triage_grievance"], other)
        for actor in [outsider, self.mentor]:
            with self.assertRaises(NotFound):
                q.grievance_detail(actor=actor, pk=obj.pk)
        with self.assertRaises(NotFound):
            s.grievance_action(
                actor=staff,
                pk=obj.pk,
                expected_status="SUBMITTED",
                action="assign",
                notes="Route",
                department_id=other.pk,
            )
        s.grievance_action(
            actor=staff,
            pk=obj.pk,
            expected_status="SUBMITTED",
            action="assign",
            notes="Route",
            department_id=self.department.pk,
        )

    def test_inactive_category_and_number_collision_retry(self):
        first = self.grievance()
        with patch.object(
            s.GrievanceNumberGenerator,
            "next",
            side_effect=[first.grievance_number, "TEST-SECOND"],
        ):
            second = self.grievance()
        self.assertNotEqual(first.grievance_number, second.grievance_number)
        s.category_write(
            actor=self.root,
            pk=self.category.pk,
            category_code="TEST",
            category_name="Test only",
            is_active=False,
        )
        with self.assertRaises(NotFound):
            self.grievance()

    def test_action_immutable_and_vocabulary(self):
        obj = self.grievance()
        row = m.GrievanceAction.objects.get(grievance=obj)
        with self.assertRaises(ModelError):
            row.save()
        with self.assertRaises(ModelError):
            m.GrievanceAction.objects.filter(pk=row.pk).update(new_status="CLOSED")
        with self.assertRaises(ModelError):
            m.GrievanceAction.objects.create(
                grievance=obj, action_type="HACK", new_status="INVALID"
            )

    def test_api_rejects_spoofing_patch_and_redacts_lists(self):
        client = APIClient()
        client.force_authenticate(self.user)
        bad = client.post(
            "/api/v1/support/own-grievances/submit/",
            {
                "student_id": 999,
                "grievance_category_id": self.category.pk,
                "subject": "Test",
                "description": "Private",
            },
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        obj = self.grievance()
        self.assertEqual(
            client.patch(
                f"/api/v1/support/grievances/{obj.pk}/",
                {"status": "CLOSED"},
                format="json",
            ).status_code,
            405,
        )
        result = client.get("/api/v1/support/own-grievances/")
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("SECRET", str(result.data))
        self.assertEqual(result["Cache-Control"], "private, no-store")
        client.force_authenticate(self.mentor)
        self.assertEqual(
            client.get(f"/api/v1/support/grievances/{obj.pk}/").status_code, 404
        )
        client.force_authenticate(None)
        self.assertIn(client.get("/api/v1/support/grievances/").status_code, [401, 403])

    def test_query_budget_reports_no_narratives(self):
        self.grievance()
        with CaptureQueriesContext(connection) as queries:
            data = q.report(self.root)
        self.assertLessEqual(len(queries), 2)
        self.assertNotIn("SECRET", str(data))
        self.assertIn("No institutional SLA", data["sla"])

    def test_revocation_and_feature_gate(self):
        row = self.session()
        Membership.objects.filter(user=self.mentor).update(is_active=False)
        with self.assertRaises(NotFound):
            q.session_detail(actor=self.mentor, pk=row.pk)
        with override_settings(STUDENT_SUPPORT_ENABLED=False):
            self.assertEqual(p.grievances(self.root).count(), 0)

    def test_student_cannot_read_another_students_grievance(self):
        obj = self.grievance()
        other = people.Student.objects.create(
            institution=self.institution,
            student_number="OTHER",
            first_name="Other",
            display_name="Other",
            student_status="ACTIVE",
        )
        user = self.actor(
            "other-student",
            ["view_own_grievance", "submit_own_grievance", "view_counselling_normal"],
        )
        people.AccountLink.objects.create(user=user, student=other)
        with self.assertRaises(NotFound):
            q.grievance_detail(actor=user, pk=obj.pk)
        self.assertFalse(p.assignments(user).exists())
        self.assertFalse(p.sessions(user).exists())

    def test_inactive_student_cannot_submit_but_can_read_own_history(self):
        obj = self.grievance()
        self.student.student_status = "SUSPENDED"
        self.student.save()
        with self.assertRaises(NotFound):
            self.grievance()
        self.assertEqual(
            q.grievance_detail(actor=self.user, pk=obj.pk)["id"], str(obj.pk)
        )

    def test_cancel_and_reject_preserve_history(self):
        ended = s.end_assignment(
            actor=self.root,
            pk=self.assignment.pk,
            expected_status="ACTIVE",
            end_date=timezone.localdate(),
            cancel=True,
        )
        self.assertEqual(ended.assignment_status, "CANCELLED")
        with self.assertRaises(s.Conflict):
            self.session()
        obj = self.grievance()
        s.grievance_action(
            actor=self.root,
            pk=obj.pk,
            expected_status="SUBMITTED",
            action="reject",
            notes="Protected rationale",
        )
        obj = s.grievance_action(
            actor=self.root, pk=obj.pk, expected_status="REJECTED", action="close"
        )
        self.assertIsNone(obj.resolved_at)
        self.assertIsNone(obj.resolution)
        self.assertEqual(m.GrievanceAction.objects.filter(grievance=obj).count(), 3)

    def test_admin_is_read_only_and_omits_notes(self):
        from django.contrib.admin.sites import AdminSite
        from rest_framework.test import APIRequestFactory

        from apps.student_support.admin import SessionAdmin

        request = APIRequestFactory().get("/admin/")
        request.user = self.mentor
        admin = SessionAdmin(m.CounsellingSession, AdminSite())
        row = self.session()
        self.assertIn(row, list(admin.get_queryset(request)))
        self.assertNotIn("observations", admin.fields)
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))

    def test_scope_limits_and_cross_institution_are_fail_closed(self):
        obj = self.grievance()
        staff = self.actor("limited", ["triage_grievance"], self.department)
        ScopeGrant.objects.filter(membership__user=staff).update(
            record_limits={"students": [self.student.pk]}
        )
        with self.assertRaises(NotFound):
            q.grievance_detail(actor=staff, pk=obj.pk)
        with (
            override_settings(STUDENT_SUPPORT_INSTITUTIONS=[]),
            self.assertRaises(NotFound),
        ):
            q.grievance_detail(actor=self.user, pk=obj.pk)

    def test_queue_query_budget_and_narrative_projection(self):
        self.grievance()
        client = APIClient()
        client.force_authenticate(self.root)
        with CaptureQueriesContext(connection) as queries:
            result = client.get("/api/v1/support/grievances/")
        self.assertEqual(result.status_code, 200)
        self.assertLessEqual(len(queries), 3)
        self.assertNotIn("SECRET", str(result.data))
        selects = [row["sql"] for row in queries if "SELECT" in row["sql"]]
        self.assertTrue(selects)
        self.assertFalse(any("`grievance`.`description`" in sql for sql in selects))
