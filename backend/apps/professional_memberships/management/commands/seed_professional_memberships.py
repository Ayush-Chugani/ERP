from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    VerificationStatus,
)


class Command(BaseCommand):
    help = "Install M31 workflow and permission configuration; never grant access to users."

    @transaction.atomic
    def handle(self, *args, **options):
        actions = {
            a.action_code: a
            for a in iam.AccessAction.objects.filter(
                action_code__in=[
                    "READ",
                    "CREATE",
                    "UPDATE",
                    "DELETE",
                    "VERIFY",
                    "APPROVE",
                    "EXPORT",
                ]
            )
        }
        if len(actions) != 7:
            raise CommandError("Install the M15 action catalogue first.")
        kind, _ = ActivityType.objects.get_or_create(
            activity_type_code="PROFESSIONAL_MEMBERSHIP",
            defaults={
                "activity_type_name": "Membership activity",
                "activity_group": "MEMBERSHIP",
            },
        )
        if kind.activity_group != "MEMBERSHIP" or not kind.is_active:
            raise CommandError(
                "Existing PROFESSIONAL_MEMBERSHIP configuration is incompatible; review it explicitly."
            )
        for model, codes in [
            (
                ApprovalStatus,
                [
                    "DRAFT",
                    "SUBMITTED",
                    "UNDER_REVIEW",
                    "RETURNED",
                    "VERIFIED",
                    "APPROVED",
                    "REJECTED",
                    "WITHDRAWN",
                ],
            ),
            (VerificationStatus, ["PENDING", "VERIFIED"]),
        ]:
            for code in codes:
                terminal = code in {"APPROVED", "REJECTED", "WITHDRAWN"} or (
                    model == VerificationStatus and code == "VERIFIED"
                )
                value, _ = model.objects.get_or_create(
                    status_code=code,
                    defaults={
                        "status_name": code.replace("_", " ").title(),
                        "is_terminal": terminal,
                    },
                )
                if not value.is_active or value.is_terminal != terminal:
                    raise CommandError(
                        "Existing workflow configuration needs review: " + code
                    )
        module, _ = iam.AccessModule.objects.get_or_create(
            module_code="PROFESSIONAL_MEMBERSHIPS",
            defaults={"module_name": "Membership activities"},
        )
        resource, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="ACTIVITY",
            defaults={"resource_name": "Membership activity"},
        )
        count = 0
        for code, action in actions.items():
            _, created = iam.Permission.objects.get_or_create(
                permission_code=f"PROFESSIONAL_MEMBERSHIPS.ACTIVITY.{code}",
                defaults={
                    "access_resource": resource,
                    "access_action": action,
                    "permission_name": f"Membership activity {code.lower()}",
                },
            )
            count += created
        master, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="MASTER",
            defaults={"resource_name": "Membership types"},
        )
        _, master_created = iam.Permission.objects.get_or_create(
            permission_code="PROFESSIONAL_MEMBERSHIPS.MASTER.UPDATE",
            defaults={
                "access_resource": master,
                "access_action": actions["UPDATE"],
                "permission_name": "Maintain membership types",
            },
        )
        count += master_created
        self.stdout.write(
            f"Created {count} permissions and installed required workflow defaults. No role or user grants changed."
        )
