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
    help = "Install M26 configuration without granting access or enabling the module."

    @transaction.atomic
    def handle(self, *args, **options):
        kind, _ = ActivityType.objects.get_or_create(
            activity_type_code="FUNDED_RESEARCH_PROJECT",
            defaults={
                "activity_type_name": "Funded research project",
                "activity_group": "RESEARCH",
            },
        )
        if not kind.is_active or kind.activity_group != "RESEARCH":
            raise CommandError(
                "Review incompatible funded project activity configuration."
            )
        for model, codes in [
            (ApprovalStatus, ["APPROVED"]),
            (VerificationStatus, ["PENDING"]),
            (
                ResearchStatus,
                ["SANCTIONED", "ONGOING", "COMPLETED", "CLOSED", "CANCELLED"],
            ),
        ]:
            for index, code in enumerate(codes):
                terminal = code in {"APPROVED", "CLOSED", "CANCELLED"}
                row, _ = model.objects.get_or_create(
                    status_code=code,
                    defaults={"status_name": code.title(), "is_terminal": terminal},
                )
                if not row.is_active or row.is_terminal != terminal:
                    raise CommandError(
                        "Review incompatible status configuration: " + code
                    )
        module, _ = iam.AccessModule.objects.get_or_create(
            module_code="FUNDED_PROJECTS",
            defaults={"module_name": "Funded research projects"},
        )
        for resource, actions in {
            "ACTIVITY": ["READ", "CREATE", "UPDATE", "DELETE", "EXPORT"],
            "STATUS": ["UPDATE"],
            "FINANCE": ["READ", "UPDATE", "DELETE", "EXPORT"],
        }.items():
            target, _ = iam.AccessResource.objects.get_or_create(
                access_module=module,
                resource_code=resource,
                defaults={"resource_name": "Funded project " + resource.lower()},
            )
            for code in actions:
                action = iam.AccessAction.objects.filter(
                    action_code=code, is_active=True
                ).first()
                if not action:
                    raise CommandError("Install active M15 action catalogue first.")
                iam.Permission.objects.get_or_create(
                    permission_code=f"FUNDED_PROJECTS.{resource}.{code}",
                    defaults={
                        "access_resource": target,
                        "access_action": action,
                        "permission_name": f"Funded projects {resource.lower()} {code.lower()}",
                    },
                )
        self.stdout.write("M26 configuration installed; no user grants changed.")
