from typing import ClassVar

from django.db import models
from django.db.models import Q

from apps.documents_exit.fields import NativeTimestampField
from apps.people_master.fields import UnsignedBigAutoField, YearField
from apps.student_support.fields import (
    CanonicalDateTimeField,
    CanonicalTextField,
    CurrentTimestamp,
    NativeEnumField,
)


class Journal(models.Model):
    journal_id = UnsignedBigAutoField(primary_key=True)
    journal_name = models.CharField(max_length=300, db_collation="utf8mb4_unicode_ci")
    journal_type = models.ForeignKey(
        "staff_profile.JournalType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="journal_type_id",
    )
    publisher = models.ForeignKey(
        "staff_profile.Publisher",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="publisher_id",
        null=True,
        blank=True,
    )
    issn = models.CharField(
        max_length=20, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    eissn = models.CharField(
        max_length=20, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    website_url = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="country_id",
        null=True,
        blank=True,
    )
    is_peer_reviewed_default = models.BooleanField(null=True, blank=True)
    is_open_access_default = models.BooleanField(null=True, blank=True)
    is_active = models.BooleanField(db_default=True, default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)

    class Meta:
        db_table = "journal"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=["issn"], name="uq_journal_issn"),
            models.UniqueConstraint(fields=["eissn"], name="uq_journal_eissn"),
        ]


class JournalPublication(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="staff_activity_id",
        primary_key=True,
    )
    publication_type = models.ForeignKey(
        "staff_profile.PublicationType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="publication_type_id",
    )
    journal = models.ForeignKey(
        "research_publications.Journal",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="journal_id",
    )
    paper_title = models.CharField(max_length=500, db_collation="utf8mb4_unicode_ci")
    volume_number = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    issue_number = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    edition = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    page_from = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    page_to = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    article_number = models.CharField(
        max_length=60, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    publication_date = models.DateField(null=True, blank=True)
    publication_year = YearField()
    doi = models.CharField(
        max_length=255, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    url = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    peer_reviewed = models.BooleanField(db_default=False, default=False)
    open_access = models.BooleanField(db_default=False, default=False)
    primary_author_position = models.PositiveSmallIntegerField(null=True, blank=True)
    primary_staff_corresponding_author = models.BooleanField(
        db_default=False, default=False
    )
    affiliation_text = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    abstract_text = CanonicalTextField(
        db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    keywords = CanonicalTextField(
        db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )

    class Meta:
        db_table = "journal_publication"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=["doi"], name="uq_journal_publication_doi"),
        ]


class JournalPublicationIndexing(models.Model):
    staff_activity = models.ForeignKey(
        "research_publications.JournalPublication",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="staff_activity_id",
    )
    indexing_agency = models.ForeignKey(
        "staff_profile.IndexingAgency",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="indexing_agency_id",
    )
    indexed_year = YearField(null=True, blank=True)
    indexing_status = NativeEnumField(
        choices=[
            ("CLAIMED", "CLAIMED"),
            ("VERIFIED", "VERIFIED"),
            ("DISCONTINUED", "DISCONTINUED"),
            ("NOT_INDEXED", "NOT_INDEXED"),
        ],
        max_length=12,
        db_collation="utf8mb4_unicode_ci",
        db_default="CLAIMED",
        default="CLAIMED",
    )
    source_url = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    remarks = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    pk = models.CompositePrimaryKey("staff_activity_id", "indexing_agency_id")

    class Meta:
        db_table = "journal_publication_indexing"
        default_permissions = ()
        constraints: ClassVar[list] = []


class JournalMetric(models.Model):
    journal_metric_id = UnsignedBigAutoField(primary_key=True)
    journal = models.ForeignKey(
        "research_publications.Journal",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="journal_id",
    )
    metric_type = models.ForeignKey(
        "staff_profile.MetricType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="metric_type_id",
    )
    metric_year = YearField()
    metric_value = models.DecimalField(max_digits=12, decimal_places=4)
    quartile = models.CharField(
        max_length=10, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    source_name = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    source_url = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    verified_at = CanonicalDateTimeField(null=True, blank=True)

    class Meta:
        db_table = "journal_metric"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["journal", "metric_type", "metric_year"],
                name="uq_journal_metric",
            ),
            models.CheckConstraint(
                condition=Q(metric_value__gte=0), name="chk_journal_metric_value"
            ),
        ]
