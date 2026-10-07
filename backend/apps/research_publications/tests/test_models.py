"""MySQL contract tests using synthetic publications only."""

import importlib
import re
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.people_master.models import Employee
from apps.people_master.tests.test_services import fixture
from apps.research_publications.models import (
    Journal,
    JournalMetric,
    JournalPublication,
    JournalPublicationIndexing,
)
from apps.staff_activities.models import StaffActivity
from apps.staff_profile import models as refs


class PublicationModelTests(TestCase):
    def setUp(self):
        fixture(self)
        self.employee = Employee.objects.create(
            institution=self.institution,
            employment_source=self.source,
            employee_number="M21-SYNTHETIC",
            first_name="Synthetic",
            display_name="Synthetic",
            joining_date=date(2020, 1, 1),
            employment_type="REGULAR",
        )
        self.kind = refs.ActivityType.objects.create(
            activity_type_code="SYNTHETIC_JOURNAL",
            activity_type_name="Synthetic publication",
            activity_group="PUBLICATION",
        )
        self.verification = refs.VerificationStatus.objects.create(
            status_code="SYNTHETIC", status_name="Synthetic"
        )
        self.approval = refs.ApprovalStatus.objects.create(
            status_code="SYNTHETIC", status_name="Synthetic"
        )
        self.journal_type = refs.JournalType.objects.create(
            journal_type_code="SYNTHETIC", journal_type_name="Synthetic"
        )
        self.publication_type = refs.PublicationType.objects.create(
            publication_type_code="SYNTHETIC", publication_type_name="Synthetic"
        )
        self.journal = Journal.objects.create(
            journal_name="Synthetic journal", journal_type=self.journal_type
        )

    def activity(self, **kwargs):
        return StaffActivity.objects.create(
            employee=self.employee,
            institution=self.institution,
            activity_type=self.kind,
            verification_status=self.verification,
            approval_status=self.approval,
            activity_title="Synthetic paper",
            **kwargs,
        )

    def publication(self, **kwargs):
        return JournalPublication.objects.create(
            staff_activity=self.activity(),
            journal=self.journal,
            publication_type=self.publication_type,
            paper_title="Synthetic paper",
            publication_year=2026,
            **kwargs,
        )

    def test_shared_primary_key_orphan_rejection_and_protection(self):
        row = self.publication()
        self.assertEqual(row.pk, row.staff_activity_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalPublication.objects.create(
                staff_activity=row.staff_activity,
                journal=self.journal,
                publication_type=self.publication_type,
                paper_title="Duplicate child",
                publication_year=2026,
            )
        for target in (row.staff_activity, self.journal, self.publication_type):
            with self.assertRaises(ProtectedError):
                target.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalPublication.objects.create(
                staff_activity_id=999999999,
                journal=self.journal,
                publication_type=self.publication_type,
                paper_title="Missing parent",
                publication_year=2026,
            )

    def test_identifier_uniqueness_and_nullable_values(self):
        Journal.objects.create(
            journal_name="Other null ISSN", journal_type=self.journal_type
        )
        self.journal.issn = "1234-5678"
        self.journal.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Journal.objects.create(
                journal_name="Duplicate",
                journal_type=self.journal_type,
                issn="1234-5678",
            )
        self.publication()
        self.publication()
        self.publication(doi="10.0000/synthetic")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.publication(doi="10.0000/SYNTHETIC")

    def test_indexing_composite_identity(self):
        publication = self.publication()
        agency = refs.IndexingAgency.objects.create(
            agency_code="SYNTHETIC", agency_name="Synthetic"
        )
        row = JournalPublicationIndexing.objects.create(
            staff_activity=publication, indexing_agency=agency
        )
        self.assertEqual(row.pk, (publication.pk, agency.pk))
        self.assertEqual(
            JournalPublicationIndexing.objects.get(pk=row.pk).indexing_status, "CLAIMED"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalPublicationIndexing.objects.create(
                staff_activity=publication, indexing_agency=agency
            )
        with self.assertRaises(ProtectedError):
            agency.delete()

    def test_metric_uniqueness_nonnegative_and_precision(self):
        metric = refs.MetricType.objects.create(
            metric_code="SYNTHETIC", metric_name="Synthetic"
        )
        values = {"journal": self.journal, "metric_type": metric, "metric_year": 2026}
        row = JournalMetric.objects.create(**values, metric_value=Decimal("12.3456"))
        row.refresh_from_db()
        self.assertEqual(row.metric_value, Decimal("12.3456"))
        self.assertIsNone(row.verified_at)
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalMetric.objects.create(**values, metric_value=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            JournalMetric.objects.create(
                journal=self.journal,
                metric_type=metric,
                metric_year=2025,
                metric_value=-1,
            )

    def test_parent_dates_and_atomic_rollback(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.activity(start_date=date(2026, 2, 1), end_date=date(2026, 1, 1))
        self.publication(doi="10.0000/rollback")
        count = StaffActivity.objects.count()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.publication(doi="10.0000/rollback")
        self.assertEqual(StaffActivity.objects.count(), count)

    def test_historical_publication_flags_are_independent(self):
        row = self.publication(peer_reviewed=True, open_access=False)
        self.journal.is_peer_reviewed_default = False
        self.journal.is_open_access_default = True
        self.journal.save()
        row.refresh_from_db()
        self.assertTrue(row.peer_reviewed)
        self.assertFalse(row.open_access)

    def test_install_refuses_silent_adoption_and_reverse_preserves_rows(self):
        from apps.research_publications.migrations._install import install, uninstall

        with connection.schema_editor(atomic=False) as editor:
            with self.assertRaisesRegex(RuntimeError, "adoption review"):
                install(apps, editor)
            with self.assertRaisesRegex(RuntimeError, "populated"):
                uninstall(apps, editor)
        self.assertTrue(Journal.objects.filter(pk=self.journal.pk).exists())

    def test_source_schema_columns_types_and_named_constraints(self):
        self.assertEqual(connection.vendor, "mysql")
        with connection.cursor() as cursor:
            for app in ("staff_profile", "staff_activities", "research_publications"):
                ddls = importlib.import_module("apps." + app + ".migrations._ddl").DDL
                for ddl in ddls:
                    table = re.search(r"CREATE TABLE (\w+)", ddl)[1]
                    model = next(
                        m
                        for m in apps.get_app_config(app).get_models()
                        if m._meta.db_table == table
                    )
                    fields = {f.column: f for f in model._meta.local_fields if f.column}
                    cursor.execute(
                        "SELECT COLUMN_NAME,COLUMN_TYPE,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                        [table],
                    )
                    columns = {
                        n: (t.lower(), extra.lower())
                        for n, t, extra in cursor.fetchall()
                    }
                    self.assertEqual(set(fields), set(columns), table)
                    source_cols = set(
                        re.findall(
                            r"^\s*(\w+) (?:BIGINT|SMALLINT|TINYINT|VARCHAR|BOOLEAN|ENUM|TIMESTAMP|DATETIME|DATE|YEAR|TEXT|DECIMAL)\b",
                            ddl,
                            re.MULTILINE,
                        )
                    )
                    self.assertEqual(set(fields), source_cols, table)
                    for name, field in fields.items():
                        expected = (
                            field.db_type(connection)
                            .lower()
                            .replace("integer", "int")
                            .replace("bool", "tinyint(1)")
                            .replace("numeric", "decimal")
                            .replace(", ", ",")
                        )
                        self.assertEqual(columns[name][0], expected, table + "." + name)
                    if "ON UPDATE" in ddl:
                        self.assertIn(
                            "on update current_timestamp", columns["updated_at"][1]
                        )
                    for wanted, col, target, target_col in re.findall(
                        r"CONSTRAINT (\w+) FOREIGN KEY \((\w+)\)\s*REFERENCES (\w+)\((\w+)\)",
                        ddl,
                    ):
                        cursor.execute(
                            "SELECT CONSTRAINT_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",
                            [table, col],
                        )
                        self.assertEqual(
                            cursor.fetchall(), ((wanted, target, target_col),)
                        )
                    for name, cols in re.findall(
                        r"CONSTRAINT (\w+) UNIQUE\s*\(([^)]+)\)", ddl
                    ):
                        cursor.execute(
                            "SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s AND NON_UNIQUE=0 ORDER BY SEQ_IN_INDEX",
                            [table, name],
                        )
                        self.assertEqual(
                            [r[0] for r in cursor.fetchall()],
                            [c.strip() for c in cols.split(",")],
                        )
