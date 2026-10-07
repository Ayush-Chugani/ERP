from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import (
    ActivityType,
    ApprovalStatus,
    VerificationStatus,
)


class Command(BaseCommand):
    help = "Install M32 workflow and permission configuration; never grant access to users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--example-types",
            action="store_true",
            help="Install optional source catalogue examples; never overwrite existing types or require their contexts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options.get("example_types"):
            from apps.staff_profile.models import ProfessionalContributionType

            for code, label in (
                ("JOURNAL_REVIEWER", "Journal Reviewer"),
                ("SESSION_CHAIR", "Session Chair"),
                ("BOARD_OF_STUDIES", "Board of Studies Member"),
                ("OTHER", "Other Professional Contribution"),
            ):
                ProfessionalContributionType.objects.get_or_create(
                    contribution_code=code, defaults={"contribution_name": label}
                )
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
            activity_type_code="ACADEMIC_PROFESSIONAL_CONTRIBUTION",
            defaults={
                "activity_type_name": "Contribution activity",
                "activity_group": "ACADEMIC_PROFESSIONAL_CONTRIBUTION",
            },
        )
        if (
            kind.activity_group != "ACADEMIC_PROFESSIONAL_CONTRIBUTION"
            or not kind.is_active
        ):
            raise CommandError(
                "Existing ACADEMIC_PROFESSIONAL_CONTRIBUTION configuration is incompatible; review it explicitly."
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
            module_code="PROFESSIONAL_CONTRIBUTIONS",
            defaults={"module_name": "Contribution activities"},
        )
        resource, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="ACTIVITY",
            defaults={"resource_name": "Contribution activity"},
        )
        count = 0
        for code, action in actions.items():
            _, created = iam.Permission.objects.get_or_create(
                permission_code=f"PROFESSIONAL_CONTRIBUTIONS.ACTIVITY.{code}",
                defaults={
                    "access_resource": resource,
                    "access_action": action,
                    "permission_name": f"Contribution activity {code.lower()}",
                },
            )
            count += created
        master, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="MASTER",
            defaults={"resource_name": "Contribution categories"},
        )
        _, master_created = iam.Permission.objects.get_or_create(
            permission_code="PROFESSIONAL_CONTRIBUTIONS.MASTER.UPDATE",
            defaults={
                "access_resource": master,
                "access_action": actions["UPDATE"],
                "permission_name": "Maintain contribution types",
            },
        )
        count += master_created
        self.stdout.write(
            f"Created {count} permissions and installed required workflow defaults. No role or user grants changed."
        )
