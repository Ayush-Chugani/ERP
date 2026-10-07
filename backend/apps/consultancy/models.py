from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.employee_hr.fields import FixedCharField
from apps.student_support.fields import CanonicalTextField, NativeEnumField


class ConsultancyProject(models.Model):
    class Type(models.TextChoices):
        CONSULTANCY = "CONSULTANCY", "Consultancy"
        INDUSTRY_SPONSORED_PROJECT = (
            "INDUSTRY_SPONSORED_PROJECT",
            "Industry-sponsored project",
        )
        TESTING_SERVICE = "TESTING_SERVICE", "Testing service"
        TRAINING_SERVICE = "TRAINING_SERVICE", "Training service"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed"
        APPROVED = "APPROVED", "Approved"
        ONGOING = "ONGOING", "Ongoing"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        CLOSED = "CLOSED", "Closed"

    staff_activity = models.OneToOneField(
        "staff_activities.StaffActivity",
        primary_key=True,
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    client_organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        db_column="client_organization_id",
        related_name="+",
    )
    principal_consultant_employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        db_column="principal_consultant_employee_id",
        related_name="+",
    )
    consultancy_title = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci"
    )
    consultancy_type = NativeEnumField(
        max_length=30,
        choices=Type.choices,
        default=Type.CONSULTANCY,
        db_default="CONSULTANCY",
        db_collation="utf8mb4_unicode_ci",
    )
    work_order_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    agreement_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    purchase_order_number = models.CharField(
        max_length=150, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    project_start_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    consultancy_amount = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    amount_received = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, db_default=0
    )
    faculty_incentive_share = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    currency_code = FixedCharField(
        max_length=3, default="INR", db_default="INR", db_collation="utf8mb4_unicode_ci"
    )
    deliverables = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    status = NativeEnumField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROPOSED,
        db_default="PROPOSED",
        db_collation="utf8mb4_unicode_ci",
    )
    client_feedback = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "consultancy_project"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=Q(completion_date__isnull=True)
                | Q(completion_date__gte=F("project_start_date")),
                name="chk_consultancy_dates",
            ),
            models.CheckConstraint(
                condition=Q(consultancy_amount__gte=0, amount_received__gte=0)
                & (
                    Q(faculty_incentive_share__isnull=True)
                    | Q(faculty_incentive_share__gte=0)
                ),
                name="chk_consultancy_amounts",
            ),
        ]

    def __str__(self):
        return self.consultancy_title

    def clean(self):
        super().clean()
        if (
            self.completion_date
            and self.project_start_date
            and self.completion_date < self.project_start_date
        ):
            raise ValidationError(
                {"completion_date": "Completion cannot precede project start."}
            )
        if (
            self.status in {self.Status.COMPLETED, self.Status.CLOSED}
            and not self.completion_date
        ):
            raise ValidationError(
                {
                    "completion_date": "Completion date is required for completed/closed projects."
                }
            )


from apps.identity_access.model_support import Evidence


class ProjectTeam(models.Model):
    project = models.ForeignKey(
        ConsultancyProject, on_delete=models.PROTECT, related_name="team"
    )
    employee = models.ForeignKey(
        "people_master.Employee", on_delete=models.PROTECT, related_name="+"
    )
    project_role = models.CharField(max_length=80)
    contribution_description = CanonicalTextField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "platform_consultancy_team"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["project", "employee"], name="uq_consultancy_team_member"
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="chk_consultancy_team_dates",
            ),
        ]


class ProjectMilestone(models.Model):
    project = models.ForeignKey(
        ConsultancyProject, on_delete=models.PROTECT, related_name="milestones"
    )
    sequence = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = CanonicalTextField(null=True, blank=True)
    due_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    acceptance_date = models.DateField(null=True, blank=True)
    status = NativeEnumField(
        max_length=20,
        choices=[
            (v, v.title()) for v in ["PLANNED", "COMPLETED", "ACCEPTED", "CANCELLED"]
        ],
        default="PLANNED",
    )
    client_remarks = CanonicalTextField(null=True, blank=True)

    class Meta:
        db_table = "platform_consultancy_milestone"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["project", "sequence"], name="uq_consultancy_milestone_seq"
            ),
            models.CheckConstraint(
                condition=Q(sequence__gt=0), name="chk_consultancy_milestone_seq"
            ),
            models.CheckConstraint(
                condition=Q(acceptance_date__isnull=True)
                | Q(
                    completion_date__isnull=False,
                    acceptance_date__gte=F("completion_date"),
                ),
                name="chk_consultancy_acceptance",
            ),
        ]


class ProjectReceipt(Evidence):
    project = models.ForeignKey(
        ConsultancyProject, on_delete=models.PROTECT, related_name="receipts"
    )
    receipt_date = models.DateField()
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency_code = FixedCharField(max_length=3)
    reference_number = models.CharField(max_length=150)
    invoice_number = models.CharField(max_length=150, null=True, blank=True)
    payment_mode = models.CharField(max_length=80, null=True, blank=True)
    remarks = CanonicalTextField(null=True, blank=True)
    document_attachment = models.ForeignKey(
        "staff_activities.ActivityAttachment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_consultancy_receipt"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["project", "reference_number"],
                name="uq_consultancy_receipt_ref",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="chk_consultancy_receipt_amount"
            ),
        ]


class ReceiptVoid(Evidence):
    receipt = models.OneToOneField(
        ProjectReceipt, on_delete=models.PROTECT, related_name="void_record"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = CanonicalTextField()

    class Meta:
        db_table = "platform_consultancy_receipt_void"
        default_permissions = ()


class ProjectStatusHistory(Evidence):
    project = models.ForeignKey(
        ConsultancyProject, on_delete=models.PROTECT, related_name="history"
    )
    from_status = models.CharField(max_length=20, null=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    remarks = CanonicalTextField()

    class Meta:
        db_table = "platform_consultancy_status_history"
        default_permissions = ()
