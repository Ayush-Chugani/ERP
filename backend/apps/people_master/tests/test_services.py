from datetime import date
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from apps.organization.models import University, Institution, Campus, Department
from apps.common_reference.models import Country
from apps.tenancy.models import InstitutionModule, Membership, ScopeGrant
from apps.people_master import models as m
from apps.people_master.services import execute, Command, version, set_primary
from apps.people_master.exceptions import PeopleConflict, StalePeopleVersion
from apps.people_master.permissions import scoped
from apps.people_master import identity


def fixture(o):
    o.root = get_user_model().objects.create_superuser(
        username="m5root", password="test-password"
    )
    university = University.objects.create(
        university_code="M5U", university_name="University"
    )
    o.institution = Institution.objects.create(
        university=university, institution_code="M5I", institution_name="Institution"
    )
    o.campus = Campus.objects.create(
        institution=o.institution, campus_code="M5C", campus_name="Campus"
    )
    o.department = Department.objects.create(
        campus=o.campus, department_code="M5D", department_name="Department"
    )
    InstitutionModule.objects.create(institution=o.institution, people_master=True)
    o.country = Country.objects.create(country_name="Example country", iso_code="XY")
    o.source = m.EmploymentSource.objects.get_or_create(
        source_code="INSTITUTION",
        defaults={"source_name": "Institution Employee", "is_external": False},
    )[0]
    o.type = m.StaffType.objects.get_or_create(
        type_code="TEACHING", defaults={"type_name": "Teaching"}
    )[0]
    o.category = m.StaffCategory.objects.get_or_create(
        category_code="TEACHING_STAFF",
        defaults={"category_name": "Teaching Staff", "staff_type": o.type},
    )[0]
    o.designation = m.Designation.objects.get_or_create(
        designation_code="PROFESSOR",
        defaults={"designation_name": "Professor", "staff_category": o.category},
    )[0]


def student(o, number="S1"):
    return execute(
        Command(
            m.Student,
            o.root,
            {
                "student_number": number,
                "first_name": "Student",
                "display_name": "Student One",
                "institution_id": o.institution.pk,
                "campus_id": o.campus.pk,
                "department_id": o.department.pk,
            },
        )
    )


def address(o, person, start=date(2026, 1, 1)):
    model = m.StudentAddress if isinstance(person, m.Student) else m.EmployeeAddress
    parent = "student_id" if isinstance(person, m.Student) else "employee_id"
    return execute(
        Command(
            model,
            o.root,
            {
                parent: person.pk,
                "address_type": "CURRENT",
                "address_line_1": "Private road",
                "city": "City",
                "country_id": o.country.pk,
                "valid_from": start,
            },
        )
    )


@override_settings(PEOPLE_MASTER_ENABLED=True)
class PeopleServicesTests(TestCase):
    def setUp(self):
        fixture(self)

    def test_student_activation_and_primary_history(self):
        person = student(self)
        with self.assertRaises(PeopleConflict):
            execute(
                Command(
                    m.Student,
                    self.root,
                    {"status": "ACTIVE"},
                    person.pk,
                    "status",
                    version(person),
                    "Activate",
                )
            )
        row = address(self, person)
        set_primary(
            m.StudentAddress,
            row.pk,
            actor=self.root,
            expected_version=version(row),
            reason="Current address",
        )
        person = execute(
            Command(
                m.Student,
                self.root,
                {"status": "ACTIVE"},
                person.pk,
                "status",
                version(person),
                "Activate",
            )
        )
        second = address(self, person, date(2026, 2, 1))
        set_primary(
            m.StudentAddress,
            second.pk,
            actor=self.root,
            expected_version=version(second),
            reason="Moved",
        )
        row.refresh_from_db()
        self.assertEqual(row.valid_to, date(2026, 1, 31))
        self.assertEqual(
            m.StudentAddress.objects.filter(
                student=person, is_primary=True, valid_to__isnull=True
            ).count(),
            1,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.StudentAddress.objects.create(
                student=person,
                address_type="OTHER",
                address_line_1="Other",
                city="X",
                country=self.country,
                is_primary=True,
            )
        self.assertFalse(
            any("Private road" in str(a.after) for a in m.PeopleAudit.objects.all())
        )

    def test_employee_onboarding_requires_address_and_assignment(self):
        employee = execute(
            Command(
                m.Employee,
                self.root,
                {
                    "employee_number": "E1",
                    "first_name": "Employee",
                    "display_name": "Employee One",
                    "institution_id": self.institution.pk,
                    "employment_source_id": self.source.pk,
                    "joining_date": date(2026, 1, 1),
                    "employment_type": "REGULAR",
                },
            )
        )
        row = address(self, employee)
        set_primary(
            type(row),
            row.pk,
            actor=self.root,
            expected_version=version(row),
            reason="Address",
        )
        with self.assertRaises(PeopleConflict):
            execute(
                Command(
                    m.Employee,
                    self.root,
                    {"status": "ACTIVE"},
                    employee.pk,
                    "status",
                    version(employee),
                    "Activate",
                )
            )
        assignment = execute(
            Command(
                m.EmployeeAssignment,
                self.root,
                {
                    "employee_id": employee.pk,
                    "campus_id": self.campus.pk,
                    "department_id": self.department.pk,
                    "designation_id": self.designation.pk,
                    "start_date": date(2026, 1, 1),
                },
            )
        )
        self.assertFalse(assignment.is_primary)
        set_primary(
            type(assignment),
            assignment.pk,
            actor=self.root,
            expected_version=version(assignment),
            reason="Assignment",
        )
        execute(
            Command(
                m.Employee,
                self.root,
                {"status": "ACTIVE"},
                employee.pk,
                "status",
                version(employee),
                "Activate",
            )
        )

    def test_audit_failure_rollback_and_stale_version(self):
        person = student(self)
        with self.assertRaises(StalePeopleVersion):
            execute(
                Command(
                    m.Student,
                    self.root,
                    {"display_name": "New"},
                    person.pk,
                    expected_version="0",
                )
            )
        with patch.object(
            m.PeopleAudit.objects,
            "create",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                execute(
                    Command(
                        m.Student,
                        self.root,
                        {"display_name": "New"},
                        person.pk,
                        expected_version=version(person),
                    )
                )
        person.refresh_from_db()
        self.assertEqual(person.display_name, "Student One")

    def test_scope_masking_and_no_mass_assignment(self):
        person = student(self)
        from django.contrib.auth.models import Permission

        user = get_user_model().objects.create_user(username="reader", password="test")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people_master", codename="view_student"
            )
        )
        member = Membership.objects.create(user=user, institution=self.institution)
        ScopeGrant.objects.create(membership=member, role="INSTITUTION_ADMIN")
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/v1/people/students/")
        self.assertEqual(response.status_code, 200)
        row = response.data["results"][0]
        self.assertEqual(row["id"], str(person.pk))
        self.assertNotIn("primary_email", row)
        member.is_active = False
        member.save()
        self.assertEqual(client.get("/api/v1/people/students/").data["count"], 0)
        self.assertEqual(
            client.get(f"/api/v1/people/students/{person.pk}/").status_code, 404
        )
        client.force_authenticate(self.root)
        response = client.patch(
            f"/api/v1/people/students/{person.pk}/",
            {"student_status": "ACTIVE"},
            format="json",
            HTTP_IF_MATCH=version(person),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            client.delete(f"/api/v1/people/students/{person.pk}/").status_code, 405
        )

    def test_invitation_is_user_bound_and_single_use(self):
        person = student(self)
        user = get_user_model().objects.create_user(
            username="selfservice", password="test"
        )
        Membership.objects.create(user=user, institution=self.institution)
        invitation = identity.invite(
            actor=self.root,
            model=m.Student,
            pk=person.pk,
            user_id=user.pk,
            reason="Verified identity",
        )
        with self.assertRaises(NotFound):
            identity.accept(actor=self.root, token=invitation["token"])
        identity.accept(actor=user, token=invitation["token"])
        with self.assertRaises(NotFound):
            identity.accept(actor=user, token=invitation["token"])
        self.assertNotIn(invitation["token"], str(list(m.PeopleAudit.objects.values())))

    def test_nullable_uniqueness_and_local_ranges(self):
        person = student(self)
        student(self, "S2")
        with self.assertRaises(ValidationError):
            execute(
                Command(
                    m.StudentPreviousEducation,
                    self.root,
                    {
                        "student_id": person.pk,
                        "qualification_level": "UG",
                        "institution_name": "College",
                        "percentage": "101",
                    },
                )
            )
        with self.assertRaises(ValidationError):
            execute(
                Command(
                    m.Student,
                    self.root,
                    {
                        "student_number": "s1",
                        "first_name": "Duplicate",
                        "display_name": "Duplicate",
                        "institution_id": self.institution.pk,
                    },
                )
            )

    def test_provision_claim_and_no_account_hijacking(self):
        person = student(self)
        invitation = identity.provision(
            actor=self.root,
            model=m.Student,
            pk=person.pk,
            username="newlogin",
            email="new@example.test",
            reason="Onboarding verified",
        )
        user = get_user_model().objects.get(pk=invitation["user_id"])
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        identity.claim(
            token=invitation["token"], password="A-long-unique-onboarding-password-4921"
        )
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("A-long-unique-onboarding-password-4921"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        with self.assertRaises(NotFound):
            identity.claim(
                token=invitation["token"], password="Another-long-password-3921"
            )

    def test_create_api_returns_read_contract_and_bounded_queries(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        client = APIClient()
        client.force_authenticate(self.root)
        payload = {
            "student_number": "WIRE",
            "first_name": "Wire",
            "display_name": "Wire Student",
            "institution_id": str(self.institution.pk),
        }
        response = client.post("/api/v1/people/students/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsInstance(response.data["id"], str)
        self.assertEqual(response.data["student_status"], "APPLICANT")
        with CaptureQueriesContext(connection) as one:
            client.get("/api/v1/people/students/")
        for i in range(5):
            student(self, "MORE" + str(i))
        with CaptureQueriesContext(connection) as many:
            client.get("/api/v1/people/students/")
        self.assertLessEqual(len(many), len(one) + 1)

    def test_admin_scoped_and_no_delete(self):
        from django.contrib import admin
        from django.test import RequestFactory, Client

        obj = student(self)
        request = RequestFactory().get("/admin/")
        request.user = self.root
        registered = admin.site._registry[m.Student]
        self.assertFalse(registered.has_delete_permission(request, obj))
        self.assertNotIn("delete_selected", registered.get_actions(request))
        client = Client()
        client.force_login(self.root)
        response = client.get(f"/admin/people_master/student/{obj.pk}/change/")
        self.assertEqual(response.status_code, 200)

    def test_cross_department_choices_and_agency_consistency(self):
        other = Campus.objects.create(
            institution=self.institution,
            campus_code="OTHER",
            campus_name="Hidden campus",
        )
        foreign = Department.objects.create(
            campus=other, department_code="OTHER", department_name="Hidden department"
        )
        from django.contrib.auth.models import Permission

        user = get_user_model().objects.create_user(username="dept")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people_master", codename="view_student"
            )
        )
        membership = Membership.objects.create(user=user, institution=self.institution)
        ScopeGrant.objects.create(
            membership=membership,
            role="DEPARTMENT_ADMIN",
            campus=self.campus,
            department=self.department,
        )
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/v1/people/choices/students/department_id/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(foreign.pk), [r["id"] for r in response.data["results"]])
        with self.assertRaises(ValidationError):
            execute(
                Command(
                    m.Employee,
                    self.root,
                    {
                        "employee_number": "BAD",
                        "first_name": "Bad",
                        "display_name": "Bad",
                        "institution_id": self.institution.pk,
                        "employment_source_id": self.source.pk,
                        "agency_employee_number": "123",
                        "joining_date": date(2026, 1, 1),
                        "employment_type": "REGULAR",
                    },
                )
            )

    def test_masked_filter_inference_and_self_service_record_limits(self):
        from django.contrib.auth.models import Permission

        person = student(self)
        user = get_user_model().objects.create_user(username="linked")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people_master", codename="view_student"
            )
        )
        member = Membership.objects.create(user=user, institution=self.institution)
        grant = ScopeGrant.objects.create(membership=member, role="STUDENT")
        m.AccountLink.objects.create(user=user, student=person)
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get("/api/v1/people/students/").data["count"], 1)
        self.assertEqual(
            client.get("/api/v1/people/students/?caste_id=1").status_code, 400
        )
        grant.record_limits = {"students": []}
        grant.save()
        self.assertEqual(client.get("/api/v1/people/students/").data["count"], 0)

    def test_api_lifecycle_export_and_metadata(self):
        client = APIClient()
        client.force_authenticate(self.root)
        person = student(self)
        self.assertEqual(client.get("/api/v1/people/metadata/").status_code, 200)
        row = address(self, person)
        response = client.post(
            f"/api/v1/people/student-addresses/{row.pk}/set-primary/",
            {"reason": "Address"},
            format="json",
            HTTP_IF_MATCH=version(row),
        )
        self.assertEqual(response.status_code, 200, response.data)
        response = client.post(
            f"/api/v1/people/students/{person.pk}/status/",
            {"reason": "Activation", "status": "ACTIVE"},
            format="json",
            HTTP_IF_MATCH=version(person),
        )
        self.assertEqual(response.status_code, 200, response.data)
        execute(
            Command(
                m.Student,
                self.root,
                {"display_name": "=SUM(1,2)"},
                person.pk,
                expected_version=version(person),
            )
        )
        exported = client.get("/api/v1/people/students/export/")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("'=SUM", exported.content.decode())
        self.assertEqual(
            client.get("/api/v1/people/students/?ordering=notes").status_code, 400
        )
        self.assertEqual(
            client.get("/api/v1/people/students/?search=" + ("x" * 101)).status_code,
            400,
        )
        self.assertEqual(
            client.get(
                "/api/v1/people/students/?institution_id="
                + str(self.institution.pk)
                + "&ordering=-student_number"
            ).status_code,
            200,
        )

    def test_admin_bulk_rollback_and_actual_form_save(self):
        from django.contrib import admin
        from django.test import Client, RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage

        person = student(self)
        request = RequestFactory().post("/admin/", {"reason": "Activate"})
        request.user = self.root
        request.session = {}
        request._messages = FallbackStorage(request)
        registered = admin.site._registry[m.Student]
        registered.activate_records(request, m.Student.objects.filter(pk=person.pk))
        person.refresh_from_db()
        self.assertEqual(person.student_status, "APPLICANT")
        client = Client()
        client.force_login(self.root)
        response = client.post(
            "/admin/people_master/stafftype/add/",
            {
                "type_code": "TEST",
                "type_name": "Test type",
                "description": "Synthetic",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(m.StaffType.objects.filter(type_code="TEST").exists())
        self.assertTrue(
            m.PeopleAudit.objects.filter(
                resource="staff-types", source="admin"
            ).exists()
        )

    def test_public_contract_audit_integrity_and_import_rollback(self):
        from apps.people_master.public import identity as read_identity, events
        from apps.people_master.services import bulk_save

        person = student(self)
        dto = read_identity(
            actor=self.root,
            institution_id=self.institution.pk,
            kind="student",
            record_id=person.pk,
        )
        self.assertEqual(dto.id, str(person.pk))
        self.assertTrue(events(actor=self.root, institution_id=self.institution.pk))
        with self.assertRaises(NotFound):
            read_identity(
                actor=self.root,
                institution_id=999999,
                kind="student",
                record_id=person.pk,
            )
        data = {
            "student_number": "BULK",
            "first_name": "Bulk",
            "display_name": "Bulk",
            "institution_id": self.institution.pk,
        }
        with self.assertRaises(ValidationError):
            bulk_save(m.Student, [data, data], actor=self.root, reason="Import")
        self.assertFalse(m.Student.objects.filter(student_number="BULK").exists())
        event = m.PeopleAudit.objects.first()
        from django.core.exceptions import ValidationError as DjangoError

        with self.assertRaises(DjangoError):
            event.delete()
        with self.assertRaises(DjangoError):
            m.PeopleEvent.objects.all().update(event_type="changed")

    def test_account_unlink_and_global_management_are_guarded(self):
        person = student(self)
        user = get_user_model().objects.create_user(
            username="accountuser", email="old@example.test", password="test"
        )
        Membership.objects.create(user=user, institution=self.institution)
        invitation = identity.invite(
            actor=self.root,
            model=m.Student,
            pk=person.pk,
            user_id=user.pk,
            reason="Link",
        )
        identity.accept(actor=user, token=invitation["token"])
        identity.manage_account(
            actor=self.root,
            model=m.Student,
            pk=person.pk,
            active=False,
            email="new@example.test",
            reason="Account review",
        )
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, "new@example.test")
        identity.unlink(actor=self.root, model=m.Student, pk=person.pk, reason="Unlink")
        self.assertFalse(m.AccountLink.objects.filter(student=person).exists())
        self.assertTrue(m.Student.objects.filter(pk=person.pk).exists())

    def test_assignment_public_contract_is_scoped(self):
        from apps.people_master.public import current_assignment

        employee = execute(
            Command(
                m.Employee,
                self.root,
                {
                    "employee_number": "PUBLIC",
                    "first_name": "Public",
                    "display_name": "Public employee",
                    "institution_id": self.institution.pk,
                    "employment_source_id": self.source.pk,
                    "joining_date": date(2026, 1, 1),
                    "employment_type": "REGULAR",
                },
            )
        )
        row = execute(
            Command(
                m.EmployeeAssignment,
                self.root,
                {
                    "employee_id": employee.pk,
                    "campus_id": self.campus.pk,
                    "department_id": self.department.pk,
                    "designation_id": self.designation.pk,
                    "start_date": date(2026, 1, 1),
                },
            )
        )
        set_primary(
            type(row),
            row.pk,
            actor=self.root,
            expected_version=version(row),
            reason="Assign",
        )
        self.assertEqual(
            current_assignment(
                actor=self.root,
                institution_id=self.institution.pk,
                employee_id=employee.pk,
            ).id,
            str(row.pk),
        )
        self.assertIsNone(
            current_assignment(
                actor=self.root, institution_id=99999, employee_id=employee.pk
            )
        )

    def test_seed_repetition_preserves_administrator_edits(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection

        seed = import_module("apps.people_master.migrations.0004_staff_baseline").seed
        with connection.schema_editor() as editor:
            seed(apps, editor)
        self.type.description = "Administrator edit"
        self.type.save()
        counts = [
            model.objects.count()
            for model in (
                m.StaffType,
                m.StaffCategory,
                m.EmploymentSource,
                m.Designation,
            )
        ]
        with connection.schema_editor() as editor:
            seed(apps, editor)
            seed(apps, editor)
        self.type.refresh_from_db()
        self.assertEqual(self.type.description, "Administrator edit")
        self.assertEqual(
            counts,
            [
                model.objects.count()
                for model in (
                    m.StaffType,
                    m.StaffCategory,
                    m.EmploymentSource,
                    m.Designation,
                )
            ],
        )
