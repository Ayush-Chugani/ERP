from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.employee_hr.fields
import apps.student_support.fields

from ._install import install, uninstall


def guard_reverse(apps, schema_editor):
    if (
        apps.get_model("awards", "StaffAward").objects.exists()
        or apps.get_model("awards", "AwardStatusHistory").objects.exists()
    ):
        raise RuntimeError(
            "Retain populated awards and history; disable runtime instead."
        )


class Migration(migrations.Migration):
    atomic = False

    initial = True

    dependencies: ClassVar[list] = [
        ("staff_activities", "0003_activityattachment_activitycommandreceipt"),
        ("staff_profile", "0007_awardcategory"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    generated: ClassVar[list] = [
        migrations.CreateModel(
            name="StaffAward",
            fields=[
                (
                    "staff_activity",
                    models.OneToOneField(
                        db_column="staff_activity_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="+",
                        serialize=False,
                        to="staff_activities.staffactivity",
                    ),
                ),
                (
                    "award_name",
                    models.CharField(db_collation="utf8mb4_unicode_ci", max_length=500),
                ),
                ("award_date", models.DateField()),
                (
                    "citation_details",
                    apps.student_support.fields.CanonicalTextField(
                        blank=True, db_collation="utf8mb4_unicode_ci", null=True
                    ),
                ),
                (
                    "cash_prize_amount",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=14, null=True
                    ),
                ),
                (
                    "incentive_amount",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=14, null=True
                    ),
                ),
                (
                    "currency_code",
                    apps.employee_hr.fields.FixedCharField(
                        db_collation="utf8mb4_unicode_ci",
                        db_default="INR",
                        default="INR",
                        max_length=3,
                    ),
                ),
                (
                    "award_reference_number",
                    models.CharField(
                        blank=True,
                        db_collation="utf8mb4_unicode_ci",
                        max_length=150,
                        null=True,
                    ),
                ),
                (
                    "award_category",
                    models.ForeignKey(
                        blank=True,
                        db_column="award_category_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.awardcategory",
                    ),
                ),
                (
                    "awarding_organization",
                    models.ForeignKey(
                        blank=True,
                        db_column="awarding_organization_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.externalorganization",
                    ),
                ),
            ],
            options={
                "db_table": "staff_award",
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="AwardStatusHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "remarks",
                    apps.student_support.fields.CanonicalTextField(
                        blank=True, default=""
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "from_status",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.approvalstatus",
                    ),
                ),
                (
                    "to_status",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.approvalstatus",
                    ),
                ),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="history",
                        to="awards.staffaward",
                    ),
                ),
            ],
            options={
                "db_table": "platform_awards_status_history",
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="staffaward",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("cash_prize_amount__isnull", True),
                        ("cash_prize_amount__gte", 0),
                        _connector="OR",
                    ),
                    models.Q(
                        ("incentive_amount__isnull", True),
                        ("incentive_amount__gte", 0),
                        _connector="OR",
                    ),
                ),
                name="chk_staff_award_amounts",
            ),
        ),
    ]

    operations: ClassVar[list] = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(install, uninstall)],
            state_operations=[generated[0], generated[2]],
        ),
        generated[1],
        migrations.RunPython(migrations.RunPython.noop, guard_reverse),
    ]
