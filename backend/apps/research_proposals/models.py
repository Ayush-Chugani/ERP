from typing import ClassVar

from django.db import models
from django.db.models import Q

from apps.employee_hr.fields import FixedCharField
from apps.identity_access.model_support import Evidence
from apps.student_support.fields import CanonicalTextField


class ResearchProposal(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    principal_investigator_employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        db_column="principal_investigator_employee_id",
        related_name="+",
        null=False,
        blank=False,
    )
    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.PROTECT,
        db_column="department_id",
        related_name="+",
        null=False,
        blank=False,
    )
    funding_agency = models.ForeignKey(
        "staff_profile.FundingAgency",
        on_delete=models.PROTECT,
        db_column="funding_agency_id",
        related_name="+",
        null=True,
        blank=True,
    )
    funding_type = models.ForeignKey(
        "staff_profile.FundingType",
        on_delete=models.PROTECT,
        db_column="funding_type_id",
        related_name="+",
        null=True,
        blank=True,
    )
    research_status = models.ForeignKey(
        "staff_profile.ResearchStatus",
        on_delete=models.PROTECT,
        db_column="research_status_id",
        related_name="+",
        null=False,
        blank=False,
    )
    proposal_title = models.CharField(
        max_length=500, null=False, blank=False, db_collation="utf8mb4_unicode_ci"
    )
    scheme_program_name = models.CharField(
        max_length=300, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    proposal_reference_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    research_domain = models.CharField(
        max_length=300, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    project_objectives = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    expected_outcomes = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    review_comments = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    proposal_submission_date = models.DateField(null=True, blank=True)
    requested_amount = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    currency_code = FixedCharField(
        max_length=3, default="INR", db_default="INR", db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "research_proposal"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(requested_amount__isnull=True) | Q(requested_amount__gte=0),
                name="chk_research_proposal_requested_amount",
            )
        ]


class ResearchProposalStatusHistory(Evidence):
    proposal = models.ForeignKey(
        ResearchProposal, on_delete=models.PROTECT, related_name="history"
    )
    from_status = models.ForeignKey(
        "staff_profile.ResearchStatus",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
    )
    to_status = models.ForeignKey(
        "staff_profile.ResearchStatus", on_delete=models.PROTECT, related_name="+"
    )
    changed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    remarks = CanonicalTextField(blank=True, default="")

    class Meta:
        db_table = "platform_research_proposal_status_history"
        default_permissions = ()
