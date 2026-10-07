from typing import ClassVar

from django.db import models

from apps.employee_hr.fields import FixedCharField
from apps.identity_access.model_support import Evidence
from apps.student_support.fields import CanonicalTextField


class StaffAward(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    award_category = models.ForeignKey(
        "staff_profile.AwardCategory",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="award_category_id",
        related_name="+",
    )
    awarding_organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="awarding_organization_id",
        related_name="+",
    )
    award_name = models.CharField(max_length=500, db_collation="utf8mb4_unicode_ci")
    award_date = models.DateField()
    citation_details = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    cash_prize_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    incentive_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency_code = FixedCharField(
        max_length=3, default="INR", db_default="INR", db_collation="utf8mb4_unicode_ci"
    )
    award_reference_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "staff_award"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=(
                    models.Q(cash_prize_amount__isnull=True)
                    | models.Q(cash_prize_amount__gte=0)
                )
                & (
                    models.Q(incentive_amount__isnull=True)
                    | models.Q(incentive_amount__gte=0)
                ),
                name="chk_staff_award_amounts",
            )
        ]


class AwardStatusHistory(Evidence):
    activity = models.ForeignKey(
        StaffAward, on_delete=models.PROTECT, related_name="history"
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
        db_table = "platform_awards_status_history"
        default_permissions = ()
