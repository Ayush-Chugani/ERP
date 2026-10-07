from typing import ClassVar

from django.db import models

from apps.identity_access.model_support import Evidence
from apps.student_support.fields import CanonicalTextField, NativeEnumField


class StaffProfessionalMembership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"
        LIFETIME = "LIFETIME", "Lifetime"

    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        db_column="organization_id",
        related_name="+",
    )
    membership_type = models.ForeignKey(
        "staff_profile.MembershipType",
        on_delete=models.PROTECT,
        db_column="membership_type_id",
        related_name="+",
    )
    membership_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    membership_start_date = models.DateField(null=True, blank=True)
    membership_expiry_date = models.DateField(null=True, blank=True)
    is_lifetime_membership = models.BooleanField(default=False, db_default=False)
    role_type = models.ForeignKey(
        "staff_profile.RoleType",
        on_delete=models.PROTECT,
        db_column="role_type_id",
        related_name="+",
        null=True,
        blank=True,
    )
    participation_level = models.ForeignKey(
        "staff_profile.ParticipationLevel",
        on_delete=models.PROTECT,
        db_column="participation_level_id",
        related_name="+",
        null=True,
        blank=True,
    )
    renewal_required = models.BooleanField(default=False, db_default=False)
    membership_status = NativeEnumField(
        max_length=9,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_default="ACTIVE",
        db_collation="utf8mb4_unicode_ci",
    )

    class Meta:
        db_table = "staff_professional_membership"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=("organization", "membership_number"),
                name="uq_staff_membership_number",
            ),
            models.CheckConstraint(
                condition=models.Q(membership_expiry_date__isnull=True)
                | models.Q(membership_start_date__isnull=True)
                | models.Q(
                    membership_expiry_date__gte=models.F("membership_start_date")
                ),
                name="chk_staff_membership_dates",
            ),
        ]


class MembershipStatusHistory(Evidence):
    activity = models.ForeignKey(
        StaffProfessionalMembership, on_delete=models.PROTECT, related_name="history"
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
        db_table = "platform_professional_memberships_status_history"
        default_permissions = ()
