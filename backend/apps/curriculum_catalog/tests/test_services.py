from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction, connection
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from apps.organization.models import (
    University,
    Institution,
    Campus,
    Department,
    Programme,
    ProgrammeSpecialization,
)
from apps.academic_calendar.models import Semester
from apps.tenancy.models import InstitutionModule, Membership, ScopeGrant
from apps.curriculum_catalog.models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
    CurriculumAudit,
    CurriculumEvent,
)
from apps.curriculum_catalog.services import (
    save,
    execute,
    Command,
    version,
    Conflict,
    StaleVersion,
    readiness,
)
from apps.curriculum_catalog.composition import clone_scheme, bulk_compose, reorder


def fixture(owner):
    owner.root = get_user_model().objects.create_superuser(
        username="root", password="test"
    )
    owner.user = get_user_model().objects.create_user(
        username="editor", password="test"
    )
    uni = University.objects.create(university_code="U", university_name="University")
    owner.institution = Institution.objects.create(
        university=uni, institution_code="A", institution_name="A"
    )
    other = Institution.objects.create(
        university=uni, institution_code="B", institution_name="B"
    )
    campus = Campus.objects.create(
        institution=owner.institution, campus_code="C", campus_name="Campus"
    )
    other_campus = Campus.objects.create(
        institution=other, campus_code="D", campus_name="Other"
    )
    owner.department = Department.objects.create(
        campus=campus, department_code="D", department_name="Department"
    )
    owner.foreign_department = Department.objects.create(
        campus=other_campus, department_code="D", department_name="Other"
    )
    owner.programme = Programme.objects.create(
        department=owner.department,
        programme_code="P",
        programme_name="Programme",
        programme_level="UG",
        duration_semesters=6,
    )
    owner.semester = Semester.objects.create(
        semester_number=1, semester_name="Semester 1"
    )
    owner.activation = InstitutionModule.objects.create(
        institution=owner.institution,
        organization_structure=True,
        academic_calendar=True,
        curriculum_catalog=True,
    )
    member = Membership.objects.create(user=owner.user, institution=owner.institution)
    owner.grant = ScopeGrant.objects.create(membership=member, role="INSTITUTION_ADMIN")
    owner.user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label__in=["curriculum_catalog", "academic_calendar"]
        )
    )
    owner.category = save(
        CourseCategory,
        {"category_code": "CORE", "category_name": "Core"},
        actor=owner.root,
    )
    owner.course = save(CourseCatalog, course_values(owner, "C1"), actor=owner.root)
    owner.scheme = save(
        CurriculumScheme, scheme_values(owner, "SCHEME"), actor=owner.root
    )


def course_values(owner, code, **overrides):
    result = {
        "owning_department_id": owner.department.pk,
        "course_category_id": owner.category.pk,
        "course_code": code,
        "course_title": code,
        "course_type": "THEORY",
        "credits": Decimal("3.0"),
    }
    result.update(overrides)
    return result


def scheme_values(owner, code, **overrides):
    result = {
        "programme_id": owner.programme.pk,
        "scheme_code": code,
        "scheme_name": code,
        "regulation_year": 2026,
        "total_credits": Decimal("3.0"),
        "effective_from": date(2026, 6, 1),
    }
    result.update(overrides)
    return result


def mapping_values(owner, course=None, **overrides):
    result = {
        "curriculum_scheme_id": owner.scheme.pk,
        "semester_id": owner.semester.pk,
        "course_id": (course or owner.course).pk,
        "course_category_id": owner.category.pk,
        "internal_max_marks": Decimal("40"),
        "external_max_marks": Decimal("60"),
        "passing_marks": Decimal("40"),
    }
    result.update(overrides)
    return result


class CurriculumServiceTests(TestCase):
    def setUp(self):
        fixture(self)

    def test_lifecycle_versioning_clone_and_overlap(self):
        old = version(self.scheme)
        row = save(CurriculumCourse, mapping_values(self), actor=self.root)
        self.assertNotEqual(version(self.scheme), old)
        with self.assertRaises(StaleVersion):
            execute(
                Command(
                    CurriculumScheme,
                    self.root,
                    pk=self.scheme.pk,
                    action="activate",
                    expected_version=old,
                    reason="Reviewed",
                )
            )
        self.assertTrue(readiness(self.scheme, self.root)["ready"])
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
        with self.assertRaises(Conflict):
            save(
                CurriculumCourse,
                {"passing_marks": Decimal(30)},
                actor=self.root,
                pk=row.pk,
                expected_version=version(row),
            )
        clone = clone_scheme(
            self.scheme.pk,
            actor=self.root,
            expected_version=version(self.scheme),
            values={"scheme_code": "COPY"},
            reason="Next version",
        )
        self.assertEqual(clone.status, "DRAFT")
        self.assertEqual(clone.composition.count(), 1)
        with self.assertRaises(Conflict):
            execute(
                Command(
                    CurriculumScheme,
                    self.root,
                    pk=clone.pk,
                    action="activate",
                    expected_version=version(clone),
                    reason="Reviewed",
                )
            )

    def test_electives_marks_semester_and_bulk_rollback(self):
        second = save(CourseCatalog, course_values(self, "C2"), actor=self.root)
        first = save(
            CurriculumCourse,
            mapping_values(self, is_mandatory=False, elective_group_code="E"),
            actor=self.root,
        )
        save(
            CurriculumCourse,
            mapping_values(self, second, is_mandatory=False, elective_group_code="E"),
            actor=self.root,
        )
        self.assertEqual(readiness(self.scheme, self.root)["selected_credits"], "3.0")
        unequal = save(
            CourseCatalog,
            course_values(self, "C3", credits=Decimal("4.0")),
            actor=self.root,
        )
        with self.assertRaises(ValidationError):
            save(
                CurriculumCourse,
                mapping_values(
                    self, unequal, is_mandatory=False, elective_group_code="E"
                ),
                actor=self.root,
            )
        self.assertEqual(self.scheme.composition.count(), 2)
        third = save(CourseCatalog, course_values(self, "C4"), actor=self.root)
        count = CurriculumAudit.objects.count()
        with self.assertRaises(ValidationError):
            bulk_compose(
                self.scheme.pk,
                actor=self.root,
                expected_version=version(self.scheme),
                changes=[
                    {"values": mapping_values(self, third)},
                    {
                        "values": mapping_values(
                            self, unequal, passing_marks=Decimal(500)
                        )
                    },
                ],
            )
        self.assertEqual(self.scheme.composition.count(), 2)
        self.assertEqual(CurriculumAudit.objects.count(), count)
        seventh = Semester.objects.create(semester_number=7, semester_name="Seven")
        with self.assertRaises(ValidationError):
            save(
                CurriculumCourse,
                mapping_values(self, third, semester_id=seventh.pk),
                actor=self.root,
            )

    def test_cycles_and_immutable_prerequisites(self):
        second = save(CourseCatalog, course_values(self, "C2"), actor=self.root)
        third = save(CourseCatalog, course_values(self, "C3"), actor=self.root)
        save(
            CoursePrerequisite,
            {"course_id": self.course.pk, "prerequisite_course_id": second.pk},
            actor=self.root,
        )
        save(
            CoursePrerequisite,
            {"course_id": second.pk, "prerequisite_course_id": third.pk},
            actor=self.root,
        )
        with self.assertRaises(Conflict) as error:
            save(
                CoursePrerequisite,
                {"course_id": third.pk, "prerequisite_course_id": self.course.pk},
                actor=self.root,
            )
        self.assertIn("cycle_path", error.exception.detail)
        with self.assertRaises(ValidationError):
            save(
                CoursePrerequisite,
                {"course_id": third.pk, "prerequisite_course_id": third.pk},
                actor=self.root,
            )
        save(CurriculumCourse, mapping_values(self), actor=self.root)
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
        with self.assertRaises(Conflict):
            save(
                CoursePrerequisite,
                {"course_id": self.course.pk, "prerequisite_course_id": third.pk},
                actor=self.root,
            )

    def test_scope_permissions_audit_and_rollback(self):
        with self.assertRaises(PermissionDenied):
            save(
                CourseCategory,
                {"category_code": "X", "category_name": "X"},
                actor=self.user,
            )
        with self.assertRaises(NotFound):
            save(
                CourseCatalog,
                course_values(
                    self, "FOREIGN", owning_department_id=self.foreign_department.pk
                ),
                actor=self.user,
            )
        course = save(CourseCatalog, course_values(self, "OWN"), actor=self.user)
        audit = CurriculumAudit.objects.get(
            resource="courses", record_key=str(course.pk)
        )
        self.assertEqual(audit.institution_id, self.institution.pk)
        self.assertTrue(CurriculumEvent.objects.filter(audit=audit).exists())
        with patch(
            "apps.curriculum_catalog.services.CurriculumEvent.objects.create",
            side_effect=RuntimeError("Unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                save(CourseCatalog, course_values(self, "ROLLED"), actor=self.root)
        self.assertFalse(CourseCatalog.objects.filter(course_code="ROLLED").exists())
        self.activation.curriculum_catalog = False
        self.activation.save()
        with self.assertRaises(NotFound):
            save(CourseCatalog, course_values(self, "DISABLED"), actor=self.user)

    def test_sql_composite_fk_and_bigint(self):
        other_programme = Programme.objects.create(
            department=self.department,
            programme_code="P2",
            programme_name="P2",
            programme_level="UG",
            duration_semesters=6,
        )
        specialization = ProgrammeSpecialization.objects.create(
            programme=other_programme,
            specialization_code="S",
            specialization_name="Special",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CurriculumScheme.objects.filter(pk=self.scheme.pk).update(
                specialization_id=specialization.pk
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CoursePrerequisite.objects.create(
                course=self.course, prerequisite_course=self.course
            )
        with connection.cursor() as cursor:
            cursor.execute("SHOW CREATE TABLE curriculum_course")
            self.assertIn("bigint unsigned", cursor.fetchone()[1])
            cursor.execute("SHOW CREATE TABLE course_prerequisite")
            self.assertIn(
                "PRIMARY KEY (`course_id`,`prerequisite_course_id`)",
                cursor.fetchone()[1],
            )

    def test_reorder_captures_original_before_values(self):
        second = save(CourseCatalog, course_values(self, "C2"), actor=self.root)
        a = save(
            CurriculumCourse, mapping_values(self, display_order=1), actor=self.root
        )
        b = save(
            CurriculumCourse,
            mapping_values(self, second, display_order=2),
            actor=self.root,
        )
        reorder(
            self.scheme.pk,
            actor=self.root,
            expected_version=version(self.scheme),
            semester_id=self.semester.pk,
            record_ids=[str(b.pk), str(a.pk)],
            reason="Order",
        )
        a.refresh_from_db()
        self.assertEqual(a.display_order, 2)
        event = CurriculumAudit.objects.filter(
            resource="curriculum-courses", record_key=str(a.pk), action="reorder"
        ).get()
        self.assertEqual(event.before["display_order"], 1)
        self.assertEqual(event.after["display_order"], 2)

    def test_hidden_composition_does_not_leak_through_readiness(self):
        row = save(CurriculumCourse, mapping_values(self), actor=self.root)
        self.grant.record_limits = {"curriculum-courses": []}
        self.grant.save()
        with self.assertRaises(PermissionDenied):
            readiness(self.scheme, self.user)
        with self.assertRaises(PermissionDenied):
            clone_scheme(
                self.scheme.pk,
                actor=self.user,
                expected_version=version(self.scheme),
                values={"scheme_code": "HIDDEN"},
                reason="Review",
            )
        self.assertFalse(CurriculumScheme.objects.filter(scheme_code="HIDDEN").exists())

    def test_composition_removal_and_grade_configuration(self):
        from django.test import override_settings

        row = save(CurriculumCourse, mapping_values(self), actor=self.root)
        execute(
            Command(
                CurriculumCourse,
                self.root,
                pk=row.pk,
                action="remove",
                expected_version=version(row),
                reason="Draft correction",
            )
        )
        self.assertFalse(CurriculumCourse.objects.filter(pk=row.pk).exists())
        second = save(CourseCatalog, course_values(self, "SECOND"), actor=self.root)
        with self.assertRaises(ValidationError):
            save(
                CoursePrerequisite,
                {
                    "course_id": self.course.pk,
                    "prerequisite_course_id": second.pk,
                    "minimum_grade": "A",
                },
                actor=self.root,
            )
        with override_settings(CURRICULUM_GRADE_CODES=("A", "B")):
            edge = save(
                CoursePrerequisite,
                {
                    "course_id": self.course.pk,
                    "prerequisite_course_id": second.pk,
                    "minimum_grade": "A",
                },
                actor=self.root,
            )
        execute(
            Command(
                CoursePrerequisite,
                self.root,
                pk=edge.pk,
                action="remove",
                expected_version=version(edge),
                reason="No longer required",
            )
        )
        self.assertFalse(CoursePrerequisite.objects.exists())
