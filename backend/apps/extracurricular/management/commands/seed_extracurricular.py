from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    VerificationStatus,
)


class Command(BaseCommand):
    help = "Install M29 workflow and permission configuration; never grant access to users."

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
            activity_type_code="EXTRA_CURRICULAR",
            defaults={
                "activity_type_name": "Extra-curricular activity",
                "activity_group": "EXTRA_CURRICULAR",
            },
        )
        if kind.activity_group != "EXTRA_CURRICULAR" or not kind.is_active:
            raise CommandError(
                "Existing EXTRA_CURRICULAR configuration is incompatible; review it explicitly."
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
            module_code="EXTRACURRICULAR",
            defaults={"module_name": "Extra-curricular activities"},
        )
        resource, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="ACTIVITY",
            defaults={"resource_name": "Extra-curricular activity"},
        )
        count = 0
        for code, action in actions.items():
            _, created = iam.Permission.objects.get_or_create(
                permission_code=f"EXTRACURRICULAR.ACTIVITY.{code}",
                defaults={
                    "access_resource": resource,
                    "access_action": action,
                    "permission_name": f"Extra-curricular activity {code.lower()}",
                },
            )
            count += created
        master, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="MASTER",
            defaults={"resource_name": "Extra-curricular categories"},
        )
        _, master_created = iam.Permission.objects.get_or_create(
            permission_code="EXTRACURRICULAR.MASTER.UPDATE",
            defaults={
                "access_resource": master,
                "access_action": actions["UPDATE"],
                "permission_name": "Maintain extra-curricular categories",
            },
        )
        count += master_created
        self.stdout.write(
            f"Created {count} permissions and installed required workflow defaults. No role or user grants changed."
        )
