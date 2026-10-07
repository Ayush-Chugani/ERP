from typing import ClassVar

from django.db import models

from apps.identity_access.model_support import Evidence
from apps.student_support.fields import CanonicalTextField

from .fields import UnsignedSmallCount


class StaffProfessionalContribution(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    professional_contribution_type = models.ForeignKey(
        "staff_profile.ProfessionalContributionType",
        on_delete=models.PROTECT,
        db_column="professional_contribution_type_id",
        related_name="+",
    )
    organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        db_column="organization_id",
        related_name="+",
        null=True,
        blank=True,
    )
    journal = models.ForeignKey(
        "research_publications.Journal",
        on_delete=models.PROTECT,
        db_column="journal_id",
        related_name="+",
        null=True,
        blank=True,
    )
    conference_event = models.ForeignKey(
        "conferences.ConferenceEvent",
        on_delete=models.PROTECT,
        db_column="conference_event_id",
        related_name="+",
        null=True,
        blank=True,
    )
    programme = models.ForeignKey(
        "organization.Programme",
        on_delete=models.PROTECT,
        db_column="programme_id",
        related_name="+",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        "curriculum_catalog.CourseCatalog",
        on_delete=models.PROTECT,
        db_column="course_id",
        related_name="+",
        null=True,
        blank=True,
    )
    student = models.ForeignKey(
        "people_master.Student",
        on_delete=models.PROTECT,
        db_column="student_id",
        related_name="+",
        null=True,
        blank=True,
    )
    title_topic = models.CharField(
        max_length=500, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    appointment_reference_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    contribution_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    number_of_reviews = UnsignedSmallCount(null=True, blank=True)
    number_of_candidates = UnsignedSmallCount(null=True, blank=True)
    contribution_details = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    outcome_details = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "staff_professional_contribution"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="chk_prof_contribution_dates",
            )
        ]

    def clean(self):
        from .policy import validate_contribution

        validate_contribution(self)

    def __str__(self):
        return self.title_topic or f"Professional contribution {self.pk or 'draft'}"


class ContributionStatusHistory(Evidence):
    activity = models.ForeignKey(
        StaffProfessionalContribution, on_delete=models.PROTECT, related_name="history"
    )
    from_status = models.ForeignKey(
        "staff_profile.ApprovalStatus",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
    )
    to_status = models.ForeignKey(
        "staff_profile.ApprovalStatus", on_delete=models.PROTECT, related_name="+"
    )
    changed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    remarks = CanonicalTextField(blank=True, default="")

    class Meta:
        db_table = "platform_professional_contributions_status_history"
        default_permissions = ()
