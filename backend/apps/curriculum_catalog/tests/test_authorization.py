from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib import admin
from django.db import IntegrityError, transaction, connection
from django.contrib.messages.storage.fallback import FallbackStorage
from unittest.mock import patch
from datetime import date
from decimal import Decimal
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from apps.organization.models import Department, Programme, ProgrammeSpecialization
from apps.curriculum_catalog.models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CurriculumAudit,
)
from apps.curriculum_catalog.policies import scoped
from apps.curriculum_catalog.services import save, execute, Command, version, Conflict
from apps.curriculum_catalog import public
from .test_services import fixture, course_values, mapping_values


class AuthorizationAndContractTests(TestCase):
    def setUp(self):
        fixture(self)

    def test_department_scope_and_forged_specialization(self):
        other = Department.objects.create(
            campus=self.department.campus,
            department_code="OTHER",
            department_name="Other",
        )
        hidden = save(
            CourseCatalog,
            course_values(self, "HIDDEN", owning_department_id=other.pk),
            actor=self.root,
        )
        self.grant.role = "DEPARTMENT_ADMIN"
        self.grant.campus = self.department.campus
        self.grant.department = self.department
        self.grant.full_clean()
        self.grant.save()
        self.assertFalse(scoped(CourseCatalog, self.user).filter(pk=hidden.pk).exists())
        with self.assertRaises(NotFound):
            save(
                CourseCatalog,
                {"course_title": "Attack"},
                actor=self.user,
                pk=hidden.pk,
                expected_version=version(hidden),
            )
        programme = Programme.objects.create(
            department=other,
            programme_code="OTHER",
            programme_name="Other",
            programme_level="UG",
            duration_semesters=4,
        )
        special = ProgrammeSpecialization.objects.create(
            programme=programme, specialization_code="SPEC", specialization_name="Other"
        )
        with self.assertRaises(ValidationError):
            save(
                CurriculumScheme,
                {"specialization_id": special.pk},
                actor=self.root,
                pk=self.scheme.pk,
                expected_version=version(self.scheme),
            )

    def test_missing_permission_and_inactive_membership(self):
        self.user.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="curriculum_catalog",
                codename="change_coursecatalog",
            )
        )
        with self.assertRaises(NotFound):
            save(
                CourseCatalog,
                {"course_title": "Attack"},
                actor=self.user,
                pk=self.course.pk,
                expected_version=version(self.course),
            )
        self.grant.membership.is_active = False
        self.grant.membership.save()
        self.assertFalse(scoped(CourseCatalog, self.user).exists())
        with self.assertRaises(NotFound):
            save(CourseCatalog, course_values(self, "NO"), actor=self.user)

    def test_record_limits_rollback_new_records(self):
        self.grant.record_limits = {"courses": []}
        self.grant.save()
        before = CurriculumAudit.objects.count()
        with self.assertRaises(PermissionDenied):
            save(CourseCatalog, course_values(self, "NO"), actor=self.user)
        self.assertFalse(CourseCatalog.objects.filter(course_code="NO").exists())
        self.assertEqual(before, CurriculumAudit.objects.count())

    def test_category_drift_and_referenced_course_freeze(self):
        save(CurriculumCourse, mapping_values(self), actor=self.root)
        with self.assertRaises(Conflict):
            save(
                CourseCategory,
                {"is_graded": False},
                actor=self.root,
                pk=self.category.pk,
                expected_version=version(self.category),
            )
        with self.assertRaises(Conflict):
            save(
                CourseCatalog,
                {"credits": Decimal(5)},
                actor=self.root,
                pk=self.course.pk,
                expected_version=version(self.course),
            )
        alternate = save(
            CourseCategory,
            {"category_code": "ALT", "category_name": "Alternate"},
            actor=self.root,
        )
        second = save(CourseCatalog, course_values(self, "SECOND"), actor=self.root)
        with self.assertRaises(ValidationError):
            save(
                CurriculumCourse,
                mapping_values(self, second, course_category_id=alternate.pk),
                actor=self.root,
            )

    def test_database_errors_leave_transaction_usable(self):
        with patch.object(
            CourseCatalog,
            "save",
            side_effect=IntegrityError(1062, "SQL details must not leak"),
        ):
            with self.assertRaises(Conflict) as error:
                save(CourseCatalog, course_values(self, "FAIL"), actor=self.root)
        self.assertNotIn("SQL details", str(error.exception))
        self.assertFalse(connection.needs_rollback)
        self.assertEqual(CourseCatalog.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CourseCatalog.objects.filter(pk=self.course.pk).update(credits=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CurriculumScheme.objects.filter(pk=self.scheme.pk).update(
                effective_to=date(2020, 1, 1)
            )

    def test_public_read_contracts_and_cross_scope_denial(self):
        row = save(CurriculumCourse, mapping_values(self), actor=self.root)
        kwargs = {"actor": self.user, "institution_id": self.institution.pk}
        self.assertEqual(
            public.credit_totals(**kwargs, scheme_id=self.scheme.pk)[
                "selected_credits"
            ],
            "3.0",
        )
        self.assertEqual(
            public.semester_curriculum(
                **kwargs, scheme_id=self.scheme.pk, semester_id=self.semester.pk
            )[0].id,
            str(row.pk),
        )
        self.assertEqual(
            public.elective_groups(
                **kwargs, scheme_id=self.scheme.pk, semester_id=self.semester.pk
            ),
            (),
        )
        self.assertEqual(
            public.eligibility_inputs(**kwargs, course_id=self.course.pk)[
                "course"
            ].code,
            "C1",
        )
        execute(
            Command(
                CurriculumScheme,
                self.root,
                pk=self.scheme.pk,
                action="activate",
                expected_version=version(self.scheme),
                reason="Reviewed",
            )
        )
        self.assertEqual(
            public.current_scheme(
                **kwargs,
                programme_id=self.programme.pk,
                specialization_id=None,
                on_date=date(2026, 9, 1),
            ).id,
            str(self.scheme.pk),
        )
        with self.assertRaises(PermissionDenied):
            public.course(
                actor=self.user,
                institution_id=self.foreign_department.campus.institution_id,
                course_id=self.course.pk,
            )
        with self.assertRaises(PermissionDenied):
            public.events(**kwargs)

    def test_admin_create_optimistic_form_and_atomic_bulk_failure(self):
        client = Client()
        client.force_login(self.root)
        response = client.post(
            "/admin/curriculum_catalog/coursecategory/add/",
            {
                "category_code": "ADMIN",
                "category_name": "Admin category",
                "is_graded": "on",
                "contributes_to_gpa": "on",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = CourseCategory.objects.get(category_code="ADMIN")
        self.assertTrue(
            CurriculumAudit.objects.filter(
                resource="course-categories", record_key=str(created.pk)
            ).exists()
        )
        admin_object = admin.site._registry[CurriculumScheme]
        request = RequestFactory().post("/admin/", {"reason": "Review"})
        request.user = self.root
        request.session = {}
        request._messages = FallbackStorage(request)
        admin_object.activate(
            request, CurriculumScheme.objects.filter(pk=self.scheme.pk)
        )
        self.scheme.refresh_from_db()
        self.assertEqual(self.scheme.status, "DRAFT")
        form_class = admin.site._registry[CourseCatalog].get_form(
            request, obj=self.course
        )
        form = form_class(instance=self.course)
        self.assertEqual(form.initial["expected_version"], version(self.course))

    def test_prerequisite_removal_requires_course_change_permission(self):
        from apps.curriculum_catalog.models import CoursePrerequisite

        second = save(CourseCatalog, course_values(self, "REQUIRED"), actor=self.root)
        edge = save(
            CoursePrerequisite,
            {"course_id": self.course.pk, "prerequisite_course_id": second.pk},
            actor=self.root,
        )
        self.user.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="curriculum_catalog",
                codename="change_coursecatalog",
            )
        )
        with self.assertRaises(PermissionDenied):
            execute(
                Command(
                    CoursePrerequisite,
                    self.user,
                    pk=edge.pk,
                    action="remove",
                    expected_version=version(edge),
                    reason="Remove edge",
                )
            )
        self.assertTrue(CoursePrerequisite.objects.filter(pk=edge.pk).exists())

    def test_reorder_database_failure_rolls_back_before_error_mapping(self):
        from apps.curriculum_catalog.composition import reorder

        row = save(CurriculumCourse, mapping_values(self), actor=self.root)
        before = CurriculumAudit.objects.count()
        with patch.object(
            CurriculumCourse, "save", side_effect=IntegrityError(1062, "private SQL")
        ):
            with self.assertRaises(Conflict) as error:
                reorder(
                    self.scheme.pk,
                    actor=self.root,
                    expected_version=version(self.scheme),
                    semester_id=self.semester.pk,
                    record_ids=[str(row.pk)],
                )
        self.assertNotIn("private SQL", str(error.exception))
        self.assertFalse(connection.needs_rollback)
        row.refresh_from_db()
        self.assertIsNone(row.display_order)
        self.assertEqual(before, CurriculumAudit.objects.count())
