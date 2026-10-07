from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import (
    ApprovalStatus,
    ConfidentialityLevel,
    VerificationStatus,
)

CATALOGUE = {
    "DOCUMENT": ("READ", "CREATE", "UPDATE", "DELETE", "VERIFY", "APPROVE", "EXPORT"),
    "FILE": ("READ", "CREATE", "UPDATE"),
    "HISTORY": ("READ",),
    "AUDIT": ("READ",),
    "TRASH": ("READ", "UPDATE"),
    "TAG": ("UPDATE",),
    "CLASSIFICATION": ("UPDATE",),
    "LEVEL_RESTRICTED": ("READ",),
    "LEVEL_CONFIDENTIAL": ("READ",),
    "LEVEL_HIGHLY_RESTRICTED": ("READ",),
}


class Command(BaseCommand):
    help = "Install M33 permission and workflow catalogues without granting any roles."

    @transaction.atomic
    def handle(self, *args, **options):
        actions = {a.action_code: a for a in iam.AccessAction.objects.all()}
        if {a for values in CATALOGUE.values() for a in values} - set(actions):
            raise CommandError("Install the M15 action catalogue first.")
        for model, codes in (
            (VerificationStatus, ("PENDING", "VERIFIED", "REJECTED")),
            (ApprovalStatus, ("DRAFT", "APPROVED", "REJECTED")),
        ):
            for code in codes:
                value, _ = model.objects.get_or_create(
                    status_code=code,
                    defaults={
                        "status_name": code.title(),
                        "is_terminal": code not in {"DRAFT", "PENDING"},
                    },
                )
                if not value.is_active:
                    raise CommandError(
                        "An existing workflow status is inactive; review configuration."
                    )
        for index, code in enumerate(
            ("PUBLIC", "INTERNAL", "RESTRICTED", "CONFIDENTIAL", "HIGHLY_RESTRICTED"),
            start=1,
        ):
            ConfidentialityLevel.objects.get_or_create(
                level_code=code,
                defaults={
                    "level_name": code.replace("_", " ").title(),
                    "display_order": index * 10,
                },
            )
        module, _ = iam.AccessModule.objects.get_or_create(
            module_code="EVIDENCE", defaults={"module_name": "Centralized evidence"}
        )
        count = 0
        for code, verbs in CATALOGUE.items():
            resource, _ = iam.AccessResource.objects.get_or_create(
                access_module=module,
                resource_code=code,
                defaults={"resource_name": code.replace("_", " ").title()},
            )
            for verb in verbs:
                _, created = iam.Permission.objects.get_or_create(
                    permission_code=f"EVIDENCE.{code}.{verb}",
                    defaults={
                        "access_resource": resource,
                        "access_action": actions[verb],
                        "permission_name": f"Evidence {code.lower()} {verb.lower()}",
                    },
                )
                count += created
        self.stdout.write(
            f"Created {count} permissions; no role or user grants changed."
        )
