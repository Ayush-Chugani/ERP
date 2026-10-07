from typing import ClassVar

from django.db import models
from django.db.models import F, Q

from apps.documents_exit.fields import NativeTimestampField
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import (
    CanonicalDateTimeField,
    CanonicalTextField,
    CurrentTimestamp,
)


class StaffActivity(models.Model):
    staff_activity_id = UnsignedBigAutoField(primary_key=True)
    employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="employee_id",
    )
    activity_type = models.ForeignKey(
        "staff_profile.ActivityType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="activity_type_id",
    )
    academic_year = models.ForeignKey(
        "academic_calendar.AcademicYear",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="academic_year_id",
        null=True,
        blank=True,
    )
    institution = models.ForeignKey(
        "organization.Institution",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="institution_id",
    )
    campus = models.ForeignKey(
        "organization.Campus",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="campus_id",
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="department_id",
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
    primary_role_type = models.ForeignKey(
        "staff_profile.RoleType",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="primary_role_type_id",
        null=True,
        blank=True,
    )
    activity_title = models.CharField(max_length=500, db_collation="utf8mb4_unicode_ci")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = CanonicalTextField(
        db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    outcomes = CanonicalTextField(
        db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    remarks = CanonicalTextField(
        db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    verification_status = models.ForeignKey(
        "staff_profile.VerificationStatus",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="verification_status_id",
    )
    verified_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="verified_by_user_id",
        null=True,
        blank=True,
    )
    verified_at = CanonicalDateTimeField(null=True, blank=True)
    verification_remarks = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    approval_status = models.ForeignKey(
        "staff_profile.ApprovalStatus",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="approval_status_id",
    )
    approved_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="approved_by_user_id",
        null=True,
        blank=True,
    )
    approved_at = CanonicalDateTimeField(null=True, blank=True)
    approval_remarks = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    rejection_reason = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    created_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="created_by_user_id",
        null=True,
        blank=True,
    )
    updated_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="updated_by_user_id",
        null=True,
        blank=True,
    )
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)
    deleted_at = CanonicalDateTimeField(null=True, blank=True)
    deleted_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="deleted_by_user_id",
        null=True,
        blank=True,
    )
    deletion_reason = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )

    class Meta:
        db_table = "staff_activity"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True)
                | Q(start_date__isnull=True)
                | Q(end_date__gte=F("start_date")),
                name="chk_staff_activity_dates",
            ),
        ]


class ActivityCommandReceipt(models.Model):
    """Platform extension: actor-scoped retry receipt, never an authorization grant."""

    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    operation = models.CharField(max_length=100)
    digest = models.CharField(max_length=64)
    staff_activity = models.ForeignKey(StaffActivity, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_staff_activity_receipt"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["actor", "key"], name="uq_staff_activity_receipt_actor_key"
            )
        ]


class ActivityAttachment(models.Model):
    """Retained managed-file versions; all authorization follows the parent."""

    staff_activity = models.ForeignKey(StaffActivity, on_delete=models.PROTECT)
    category = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    file_object = models.ForeignKey(
        "documents_exit.FileObject", on_delete=models.PROTECT
    )
    replaces = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_staff_activity_attachment"
        default_permissions = ()
