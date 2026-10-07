from typing import ClassVar

from django.db import models
from django.db.models import F, Q

from apps.documents_exit.fields import NativeTimestampField
from apps.employee_hr.fields import FixedCharField
from apps.identity_access.model_support import Evidence
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import CanonicalTextField, CurrentTimestamp


class FundedResearchProject(models.Model):
    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
        primary_key=True,
    )
    source_proposal_activity = models.ForeignKey(
        "research_proposals.ResearchProposal",
        on_delete=models.PROTECT,
        db_column="source_proposal_activity_id",
        related_name="+",
        null=True,
        blank=True,
    )
    project_title = models.CharField(max_length=500, db_collation="utf8mb4_unicode_ci")
    principal_investigator_employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        db_column="principal_investigator_employee_id",
        related_name="+",
    )
    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.PROTECT,
        db_column="department_id",
        related_name="+",
    )
    funding_agency = models.ForeignKey(
        "staff_profile.FundingAgency",
        on_delete=models.PROTECT,
        db_column="funding_agency_id",
        related_name="+",
    )
    funding_type = models.ForeignKey(
        "staff_profile.FundingType",
        on_delete=models.PROTECT,
        db_column="funding_type_id",
        related_name="+",
    )
    scheme_program_name = models.CharField(
        max_length=300, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    requested_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    sanctioned_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
    )
    amount_received = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    amount_utilized = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    currency_code = FixedCharField(
        max_length=3, default="INR", db_default="INR", db_collation="utf8mb4_unicode_ci"
    )
    sanction_date = models.DateField()
    sanction_order_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    project_start_date = models.DateField()
    project_end_date = models.DateField(
        null=True,
        blank=True,
    )
    duration_months = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    research_status = models.ForeignKey(
        "staff_profile.ResearchStatus",
        on_delete=models.PROTECT,
        db_column="research_status_id",
        related_name="+",
    )
    project_objectives = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    research_domain = models.CharField(
        max_length=300, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    project_outcomes = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    publications_generated = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    patents_generated = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    products_generated = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    other_outputs = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    utilization_summary = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    completion_date = models.DateField(
        null=True,
        blank=True,
    )

    class Meta:
        default_permissions = ()
        db_table = "funded_research_project"
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(
                    sanctioned_amount__gte=0,
                    amount_received__gte=0,
                    amount_utilized__gte=0,
                )
                & (Q(requested_amount__isnull=True) | Q(requested_amount__gte=0)),
                name="chk_funded_project_amounts",
            ),
            models.CheckConstraint(
                condition=Q(project_end_date__isnull=True)
                | Q(project_end_date__gte=F("project_start_date")),
                name="chk_funded_project_dates",
            ),
            models.UniqueConstraint(
                fields=["source_proposal_activity"], name="uq_project_source_proposal"
            ),
        ]
        indexes: ClassVar[list] = [
            models.Index(fields=[field], name=name)
            for field, name in [
                ("sanction_date", "ix_project_sanction"),
                ("project_start_date", "ix_project_start"),
                ("project_end_date", "ix_project_end"),
            ]
        ]

    def __str__(self):
        return self.project_title


class ResearchProjectFinancialUtilization(models.Model):
    utilization_id = UnsignedBigAutoField(primary_key=True)
    staff_activity = models.ForeignKey(
        "funded_projects.FundedResearchProject",
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    financial_year = models.CharField(
        max_length=9, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    reporting_period_from = models.DateField(
        null=True,
        blank=True,
    )
    reporting_period_to = models.DateField(
        null=True,
        blank=True,
    )
    opening_balance = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    amount_received = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    expenditure_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    closing_balance = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    utilization_certificate_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    statement_of_expenditure_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    remarks = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    created_at = NativeTimestampField(db_default=CurrentTimestamp(), editable=False)

    class Meta:
        default_permissions = ()
        db_table = "research_project_financial_utilization"
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(
                    opening_balance__gte=0,
                    amount_received__gte=0,
                    expenditure_amount__gte=0,
                    closing_balance__gte=0,
                ),
                name="chk_project_utilization_amounts",
            ),
            models.CheckConstraint(
                condition=Q(reporting_period_to__isnull=True)
                | Q(reporting_period_from__isnull=True)
                | Q(reporting_period_to__gte=F("reporting_period_from")),
                name="chk_project_utilization_dates",
            ),
        ]

    def __str__(self):
        return f"{self.staff_activity_id}: {self.reporting_period_from} - {self.reporting_period_to}"


class ProjectStatusHistory(Evidence):
    project = models.ForeignKey(
        FundedResearchProject, on_delete=models.PROTECT, related_name="history"
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
    remarks = CanonicalTextField()

    class Meta:
        db_table = "platform_funded_project_status_history"
        default_permissions = ()


class UtilizationVoid(Evidence):
    utilization = models.OneToOneField(
        ResearchProjectFinancialUtilization,
        on_delete=models.PROTECT,
        related_name="void_record",
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = CanonicalTextField()

    class Meta:
        db_table = "platform_research_utilization_void"
        default_permissions = ()
