from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    ResearchStatus,
    VerificationStatus,
)


class Command(BaseCommand):
    help = "Install M25 workflow and permission configuration; never grant access to users."

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
            activity_type_code="RESEARCH_PROPOSAL",
            defaults={
                "activity_type_name": "Research Proposal",
                "activity_group": "RESEARCH",
            },
        )
        if kind.activity_group != "RESEARCH" or not kind.is_active:
            raise CommandError(
                "Existing RESEARCH_PROPOSAL configuration is incompatible; review it explicitly."
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
        for index, code in enumerate(
            [
                "DRAFT",
                "SUBMITTED",
                "UNDER_REVIEW",
                "RETURNED",
                "VERIFIED",
                "APPROVED",
                "REJECTED",
                "WITHDRAWN",
            ]
        ):
            terminal = code in {"APPROVED", "REJECTED", "WITHDRAWN"}
            value, _ = ResearchStatus.objects.get_or_create(
                status_code=code,
                defaults={
                    "status_name": code.replace("_", " ").title(),
                    "display_order": index,
                    "is_terminal": terminal,
                },
            )
            if not value.is_active or value.is_terminal != terminal:
                raise CommandError("Existing research status requires review: " + code)
        module, _ = iam.AccessModule.objects.get_or_create(
            module_code="RESEARCH_PROPOSALS",
            defaults={"module_name": "Research Proposals"},
        )
        resource, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="ACTIVITY",
            defaults={"resource_name": "Research proposal"},
        )
        count = 0
        for code, action in actions.items():
            _, created = iam.Permission.objects.get_or_create(
                permission_code=f"RESEARCH_PROPOSALS.ACTIVITY.{code}",
                defaults={
                    "access_resource": resource,
                    "access_action": action,
                    "permission_name": f"Research proposal {code.lower()}",
                },
            )
            count += created
        self.stdout.write(
            f"Created {count} permissions and installed required workflow defaults. No role or user grants changed."
        )
