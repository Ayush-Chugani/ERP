from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase
from django.db import connections
from django.contrib.auth import get_user_model
from apps.curriculum_catalog.models import (
    CourseCatalog,
    CoursePrerequisite,
    CurriculumScheme,
    CurriculumCourse,
    CurriculumAudit,
)
from apps.curriculum_catalog.services import (
    save,
    execute,
    Command,
    version,
    Conflict,
    cycle_path,
)
from .test_services import fixture, course_values, scheme_values, mapping_values


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixture(self)

    def race(self, work):
        barrier = Barrier(2)

        def run(index):
            try:
                actor = get_user_model().objects.get(pk=self.root.pk)
                barrier.wait(timeout=10)
                work(index, actor)
                return "committed"
            except Conflict:
                return "conflict"
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertCountEqual(results, ["committed", "conflict"])

    def test_concurrent_cycle_is_impossible(self):
        second = save(CourseCatalog, course_values(self, "SECOND"), actor=self.root)
        pairs = [(self.course.pk, second.pk), (second.pk, self.course.pk)]
        self.race(
            lambda index, actor: save(
                CoursePrerequisite,
                dict(zip(["course_id", "prerequisite_course_id"], pairs[index])),
                actor=actor,
            )
        )
        self.assertEqual(CoursePrerequisite.objects.count(), 1)
        self.assertEqual(
            CurriculumAudit.objects.filter(resource="prerequisites").count(), 1
        )

    def test_concurrent_activation_and_unique_creation(self):
        second = save(CurriculumScheme, scheme_values(self, "SECOND"), actor=self.root)
        save(CurriculumCourse, mapping_values(self), actor=self.root)
        save(
            CurriculumCourse,
            mapping_values(self, curriculum_scheme_id=second.pk),
            actor=self.root,
        )
        schemes = [self.scheme, second]
        versions = [version(row) for row in schemes]
        self.race(
            lambda index, actor: execute(
                Command(
                    CurriculumScheme,
                    actor,
                    pk=schemes[index].pk,
                    action="activate",
                    expected_version=versions[index],
                    reason="Reviewed",
                )
            )
        )
        self.assertEqual(CurriculumScheme.objects.filter(status="ACTIVE").count(), 1)
        self.race(
            lambda index, actor: save(
                CourseCatalog, course_values(self, "RACE"), actor=actor
            )
        )
        self.assertEqual(CourseCatalog.objects.filter(course_code="RACE").count(), 1)


class GraphPropertiesTests(TransactionTestCase):
    def test_dags_diamonds_long_cycles_and_isolates(self):
        import random

        rng = random.Random(2026)
        for size in range(2, 45):
            edges = [
                (a, b) for a in range(size) for b in range(a) if rng.random() < 0.15
            ]
            self.assertIsNone(cycle_path(edges))
        self.assertIsNone(cycle_path([(1, 2), (1, 3), (2, 4), (3, 4)]))
        chain = [(value, value + 1) for value in range(1500)]
        self.assertIsNone(cycle_path(chain))
        self.assertTrue(cycle_path(chain + [(1500, 0)]))
        self.assertIsNone(cycle_path([]))
