from django.test import TestCase, RequestFactory, override_settings
from django.contrib import admin
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from apps.curriculum_catalog.models import (
    CourseCategory,
    CourseCatalog,
    CurriculumScheme,
    CurriculumCourse,
    CoursePrerequisite,
    CurriculumAudit,
)
from apps.curriculum_catalog.services import save, version
from apps.curriculum_catalog import public
from .test_services import fixture, course_values, mapping_values


class CurriculumAPITests(TestCase):
    def setUp(self):
        fixture(self)
        self.client = APIClient()
        self.client.force_authenticate(self.root)
        self.base = "/api/v1/curriculum/"

    def test_creation_versions_and_mass_assignment(self):
        response = self.client.post(
            self.base + "courses/",
            {**course_values(self, "API"), "credits": "3.0"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsInstance(response.data["course_id"], str)
        path = self.base + "courses/" + response.data["id"] + "/"
        self.assertEqual(
            self.client.patch(
                path, {"course_title": "Changed"}, format="json"
            ).status_code,
            400,
        )
        updated = self.client.patch(
            path,
            {"course_title": "Changed"},
            format="json",
            HTTP_IF_MATCH=response.data["version"],
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(
            self.client.patch(
                path,
                {"course_title": "Stale"},
                format="json",
                HTTP_IF_MATCH=response.data["version"],
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.patch(
                path,
                {"is_active": False},
                format="json",
                HTTP_IF_MATCH=updated.data["version"],
            ).status_code,
            400,
        )
        self.assertEqual(self.client.delete(path).status_code, 405)
        self.assertEqual(updated["Cache-Control"], "no-store")

    def test_prerequisite_pair_routes_and_large_ids(self):
        second = save(CourseCatalog, course_values(self, "C2"), actor=self.root)
        response = self.client.post(
            self.base + "prerequisites/",
            {
                "course_id": str(self.course.pk),
                "prerequisite_course_id": str(second.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn(":", response.data["id"])
        self.assertEqual(
            self.client.get(
                self.base + "prerequisites/" + response.data["id"] + "/"
            ).status_code,
            200,
        )
        row = save(CurriculumCourse, mapping_values(self), actor=self.root)
        large = 2**53 + 1
        CurriculumCourse.objects.filter(pk=row.pk).update(curriculum_course_id=large)
        response = self.client.get(self.base + f"curriculum-courses/{large}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["id"], str(large))
        self.assertEqual(response.data["curriculum_course_id"], str(large))

    def test_scope_drafts_activation_and_filters(self):
        foreign = save(
            CourseCatalog,
            course_values(
                self, "SECRET", owning_department_id=self.foreign_department.pk
            ),
            actor=self.root,
        )
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(self.base + "courses/").data["count"], 1)
        self.assertEqual(
            self.client.get(self.base + f"courses/{foreign.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.get(
                self.base + "courses/?owning_department_id=1.5"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(self.base + "courses/?ordering=password").status_code, 400
        )
        self.assertEqual(
            self.client.get(self.base + "choices/departments/").data["count"], 1
        )
        self.grant.role = "TEACHER"
        self.grant.save()
        self.assertEqual(self.client.get(self.base + "schemes/").data["count"], 0)
        self.assertFalse(
            any(
                item["can_create"]
                for item in self.client.get(self.base + "metadata/").data["resources"]
            )
        )
        self.activation.curriculum_catalog = False
        self.activation.save()
        self.assertEqual(self.client.get(self.base + "courses/").data["count"], 0)

    def test_readiness_bulk_and_clone(self):
        path = self.base + f"schemes/{self.scheme.pk}/"
        self.assertFalse(self.client.get(path + "validate/").data["ready"])
        data = {
            "changes": [
                {
                    "values": {
                        **mapping_values(self),
                        "internal_max_marks": "40",
                        "external_max_marks": "60",
                        "passing_marks": "40",
                    }
                }
            ]
        }
        response = self.client.post(
            path + "bulk-composition/",
            data,
            format="json",
            HTTP_IF_MATCH=version(self.scheme),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.client.get(path + "validate/").data["ready"])
        clone = self.client.post(
            path + "clone/",
            {"reason": "Next edition", "values": {"scheme_code": "CLONE"}},
            format="json",
            HTTP_IF_MATCH=version(self.scheme),
        )
        self.assertEqual(clone.status_code, 201, clone.data)

    def test_query_budget_admin_and_export(self):
        for index in range(5):
            save(CourseCatalog, course_values(self, f"N{index}"), actor=self.root)
        with CaptureQueriesContext(connection) as small:
            self.client.get(self.base + "courses/?page_size=1")
        with CaptureQueriesContext(connection) as large:
            self.client.get(self.base + "courses/?page_size=6")
        self.assertLessEqual(len(large), len(small) + 1)
        save(
            CourseCatalog,
            course_values(self, "FORMULA", course_title="=SUM(1,2)"),
            actor=self.root,
        )
        response = self.client.get(self.base + "courses/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=SUM", response.content.decode())
        request = RequestFactory().get("/admin/")
        request.user = self.user
        self.assertFalse(
            admin.site._registry[CourseCategory].has_add_permission(request)
        )
        self.assertFalse(
            admin.site._registry[CourseCatalog].has_delete_permission(request)
        )
        self.assertFalse(
            admin.site._registry[CurriculumAudit].has_view_permission(request)
        )
        self.assertNotIn(CoursePrerequisite, admin.site._registry)

    def test_public_graph_and_event_contract(self):
        second = save(CourseCatalog, course_values(self, "C2"), actor=self.root)
        save(
            CoursePrerequisite,
            {"course_id": self.course.pk, "prerequisite_course_id": second.pk},
            actor=self.root,
        )
        order, edges = public.prerequisite_graph(
            actor=self.root, institution_id=self.institution.pk
        )
        self.assertLess(order.index(str(second.pk)), order.index(str(self.course.pk)))
        self.assertEqual(
            public.dependency_impact(
                actor=self.root, institution_id=self.institution.pk, course_id=second.pk
            ),
            (str(self.course.pk),),
        )
        events = public.events(actor=self.root, institution_id=self.institution.pk)
        self.assertTrue(events)
        self.assertTrue(all(event["schema_version"] == 1 for event in events))

    @override_settings(CURRICULUM_CATALOG_ENABLED=False)
    def test_disabled_module(self):
        self.assertEqual(self.client.get(self.base + "courses/").status_code, 403)
        self.assertEqual(
            self.client.get("/api/v1/organization/universities/").status_code, 200
        )
