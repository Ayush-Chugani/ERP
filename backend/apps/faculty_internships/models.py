from typing import ClassVar

from django.db import models
from django.db.models import Q

from apps.employee_hr.fields import FixedCharField
from apps.student_support.fields import CanonicalTextField, NativeEnumField


class FacultyInternship(models.Model):
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
    industry_sector = models.ForeignKey(
        "staff_profile.IndustrySector",
        on_delete=models.PROTECT,
        db_column="industry_sector_id",
        null=True,
        blank=True,
        related_name="+",
    )
    internship_title = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci"
    )
    internship_domain = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    location_text = models.CharField(
        max_length=300, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    mentor_name = models.CharField(
        max_length=200, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    mentor_designation = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    mentor_email = models.CharField(
        max_length=254, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    funding_source = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    mou_reference = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    collaboration_reference = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    work_undertaken = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    technologies_tools = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    outcomes = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    stipend_incentive_type = NativeEnumField(
        max_length=10,
        choices=[
            (v, v) for v in ("NONE", "STIPEND", "INCENTIVE", "HONORARIUM", "OTHER")
        ],
        default="NONE",
        db_default="NONE",
        db_collation="utf8mb4_unicode_ci",
    )
    stipend_incentive_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency_code = FixedCharField(
        max_length=3, default="INR", db_default="INR", db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "faculty_internship"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(stipend_incentive_amount__isnull=True)
                | Q(stipend_incentive_amount__gte=0),
                name="chk_faculty_internship_amount",
            )
        ]
