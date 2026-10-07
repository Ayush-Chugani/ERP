from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.documents_exit.fields import NativeTimestampField
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import (
    CanonicalTextField,
    CurrentTimestamp,
    NativeEnumField,
)


class ConferenceEvent(models.Model):
    conference_event_id = UnsignedBigAutoField(primary_key=True)
    conference_title = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci"
    )
    conference_edition = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    organizer = models.ForeignKey(
        "staff_profile.Organizer",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="organizer_id",
        null=True,
        blank=True,
    )
    sponsoring_organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="sponsoring_organization_id",
        null=True,
        blank=True,
    )
    proceedings_publisher = models.ForeignKey(
        "staff_profile.Publisher",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="proceedings_publisher_id",
        null=True,
        blank=True,
    )
    participation_level = models.ForeignKey(
        "staff_profile.ParticipationLevel",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="participation_level_id",
        null=True,
        blank=True,
    )
    event_mode = models.ForeignKey(
        "staff_profile.EventMode",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="event_mode_id",
        null=True,
        blank=True,
    )
    venue_name = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    city = models.CharField(
        max_length=120, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    state = models.ForeignKey(
        "common_reference.State",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="state_id",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="country_id",
        null=True,
        blank=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    conference_website = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    brochure_url = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must not precede start date."})
        if (
            self.state_id
            and self.country_id
            and self.state.country_id != self.country_id
        ):
            raise ValidationError(
                {"state": "State must belong to the selected country."}
            )

    class Meta:
        db_table = "conference_event"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="chk_conference_event_dates",
            ),
        ]


class ConferenceActivity(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="staff_activity_id",
        primary_key=True,
    )
    conference_event = models.ForeignKey(
        "conferences.ConferenceEvent",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="conference_event_id",
    )
    conference_contribution_type = models.ForeignKey(
        "staff_profile.ConferenceContributionType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="conference_contribution_type_id",
    )
    publication_type = models.ForeignKey(
        "staff_profile.PublicationType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="publication_type_id",
        null=True,
        blank=True,
    )
    paper_title = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    abstract_text = CanonicalTextField(null=True, blank=True)
    proceedings_title = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    proceedings_volume = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    proceedings_issue = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    page_from = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    page_to = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    isbn = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    issn = models.CharField(
        max_length=20, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    doi = models.CharField(
        max_length=255, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    proceedings_url = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    presentation_title = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    award_name = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    award_details = CanonicalTextField(null=True, blank=True)
    award_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "conference_activity"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=["doi"], name="uq_conference_activity_doi"),
        ]


class ConferenceActivityIndexing(models.Model):
    class Status(models.TextChoices):
        CLAIMED = "CLAIMED", "Claimed"
        VERIFIED = "VERIFIED", "Verified"
        DISCONTINUED = "DISCONTINUED", "Discontinued"
        NOT_INDEXED = "NOT_INDEXED", "Not indexed"

    staff_activity = models.ForeignKey(
        "conferences.ConferenceActivity",
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
    indexing_status = NativeEnumField(
        choices=Status.choices,
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
        db_table = "conference_activity_indexing"
        default_permissions = ()
        constraints: ClassVar[list] = []
