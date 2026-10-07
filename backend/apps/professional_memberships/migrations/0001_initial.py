from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.student_support.fields

from ._install import install, uninstall


def guard_reverse(apps, schema_editor):
    if (
        apps.get_model(
            "professional_memberships", "StaffProfessionalMembership"
        ).objects.exists()
        or apps.get_model(
            "professional_memberships", "MembershipStatusHistory"
        ).objects.exists()
    ):
        raise RuntimeError("Retain populated memberships and history.")


class Migration(migrations.Migration):
    atomic = False

    initial = True

    dependencies: ClassVar[list] = [
        ("staff_activities", "0003_activityattachment_activitycommandreceipt"),
        ("staff_profile", "0008_membershiptype"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    generated: ClassVar[list] = [
        migrations.CreateModel(
            name="StaffProfessionalMembership",
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
                    "membership_number",
                    models.CharField(
                        blank=True,
                        db_collation="utf8mb4_unicode_ci",
                        max_length=150,
                        null=True,
                    ),
                ),
                ("membership_start_date", models.DateField(blank=True, null=True)),
                ("membership_expiry_date", models.DateField(blank=True, null=True)),
                (
                    "is_lifetime_membership",
                    models.BooleanField(db_default=False, default=False),
                ),
                (
                    "renewal_required",
                    models.BooleanField(db_default=False, default=False),
                ),
                (
                    "membership_status",
                    apps.student_support.fields.NativeEnumField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("EXPIRED", "Expired"),
                            ("SUSPENDED", "Suspended"),
                            ("CANCELLED", "Cancelled"),
                            ("LIFETIME", "Lifetime"),
                        ],
                        db_collation="utf8mb4_unicode_ci",
                        db_default="ACTIVE",
                        default="ACTIVE",
                        max_length=9,
                    ),
                ),
                (
                    "membership_type",
                    models.ForeignKey(
                        db_column="membership_type_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.membershiptype",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        db_column="organization_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.externalorganization",
                    ),
                ),
                (
                    "participation_level",
                    models.ForeignKey(
                        blank=True,
                        db_column="participation_level_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.participationlevel",
                    ),
                ),
                (
                    "role_type",
                    models.ForeignKey(
                        blank=True,
                        db_column="role_type_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff_profile.roletype",
                    ),
                ),
            ],
            options={
                "db_table": "staff_professional_membership",
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="MembershipStatusHistory",
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
                        to="professional_memberships.staffprofessionalmembership",
                    ),
                ),
            ],
            options={
                "db_table": "platform_professional_memberships_status_history",
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="staffprofessionalmembership",
            constraint=models.UniqueConstraint(
                fields=("organization", "membership_number"),
                name="uq_staff_membership_number",
            ),
        ),
        migrations.AddConstraint(
            model_name="staffprofessionalmembership",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("membership_expiry_date__isnull", True),
                    ("membership_start_date__isnull", True),
                    ("membership_expiry_date__gte", models.F("membership_start_date")),
                    _connector="OR",
                ),
                name="chk_staff_membership_dates",
            ),
        ),
    ]

    operations: ClassVar[list] = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(install, uninstall)],
            state_operations=[generated[0], *generated[2:]],
        ),
        generated[1],
        migrations.RunPython(migrations.RunPython.noop, guard_reverse),
    ]
