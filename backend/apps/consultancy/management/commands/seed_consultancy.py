from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import ActivityType, ApprovalStatus, VerificationStatus


class Command(BaseCommand):
    help = "Install M27 workflow/permissions without grants or activation."

    @transaction.atomic
    def handle(self, *args, **options):
        kind, _ = ActivityType.objects.get_or_create(
            activity_type_code="CONSULTANCY_PROJECT",
            defaults={
                "activity_type_name": "Consultancy project",
                "activity_group": "CONSULTANCY",
            },
        )
        if not kind.is_active or kind.activity_group != "CONSULTANCY":
            raise CommandError(
                "Review incompatible consultancy activity configuration."
            )
        for model, code, terminal in [
            (ApprovalStatus, "DRAFT", False),
            (ApprovalStatus, "APPROVED", True),
            (VerificationStatus, "PENDING", False),
        ]:
            row, _ = model.objects.get_or_create(
                status_code=code,
                defaults={"status_name": code.title(), "is_terminal": terminal},
            )
            if not row.is_active or row.is_terminal != terminal:
                raise CommandError(
                    "Review incompatible workflow configuration: " + code
                )
        module, _ = iam.AccessModule.objects.get_or_create(
            module_code="CONSULTANCY",
            defaults={"module_name": "Consultancy and industry-sponsored projects"},
        )
        for resource, actions in {
            "ACTIVITY": ["READ", "CREATE", "UPDATE", "DELETE", "EXPORT"],
            "STATUS": ["UPDATE"],
            "FINANCE": ["READ", "UPDATE", "DELETE", "EXPORT"],
            "TEAM": ["READ", "UPDATE"],
            "MILESTONE": ["READ", "UPDATE"],
            "DOCUMENT": ["READ", "UPDATE"],
        }.items():
            target, _ = iam.AccessResource.objects.get_or_create(
                access_module=module,
                resource_code=resource,
                defaults={"resource_name": "Consultancy " + resource.lower()},
            )
            for code in actions:
                action = iam.AccessAction.objects.filter(
                    action_code=code, is_active=True
                ).first()
                if not action:
                    raise CommandError("Install M15 action catalogue first.")
                iam.Permission.objects.get_or_create(
                    permission_code=f"CONSULTANCY.{resource}.{code}",
                    defaults={
                        "access_resource": target,
                        "access_action": action,
                        "permission_name": f"Consultancy {resource.lower()} {code.lower()}",
                    },
                )
        self.stdout.write("M27 configuration installed; no grants changed.")
