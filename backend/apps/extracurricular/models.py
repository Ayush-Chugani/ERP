from django.db import models

from apps.identity_access.model_support import Evidence
from apps.student_support.fields import CanonicalTextField


class ExtracurricularActivity(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    extracurricular_category = models.ForeignKey(
        "staff_profile.ExtraCurricularCategory",
        on_delete=models.PROTECT,
        db_column="extracurricular_category_id",
        related_name="+",
        null=False,
        blank=False,
    )
    organizer = models.ForeignKey(
        "staff_profile.Organizer",
        on_delete=models.PROTECT,
        db_column="organizer_id",
        related_name="+",
        null=True,
        blank=True,
    )
    institution_organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        db_column="institution_organization_id",
        related_name="+",
        null=True,
        blank=True,
    )
    state = models.ForeignKey(
        "common_reference.State",
        on_delete=models.PROTECT,
        db_column="state_id",
        related_name="+",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        db_column="country_id",
        related_name="+",
        null=True,
        blank=True,
    )
    event_name = models.CharField(
        max_length=500, null=False, blank=False, db_collation="utf8mb4_unicode_ci"
    )
    venue_name = models.CharField(
        max_length=250, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    city = models.CharField(
        max_length=120, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    award_recognition = models.CharField(
        max_length=500, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    event_date = models.DateField(null=True, blank=True)
    activity_details = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "extracurricular_activity"
        default_permissions = ()


class ExtracurricularStatusHistory(Evidence):
    activity = models.ForeignKey(
        ExtracurricularActivity, on_delete=models.PROTECT, related_name="history"
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
        db_table = "platform_extracurricular_status_history"
        default_permissions = ()
