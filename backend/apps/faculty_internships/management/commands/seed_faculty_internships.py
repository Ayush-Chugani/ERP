from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as iam
from apps.staff_profile.models import ActivityType, ApprovalStatus, VerificationStatus


class Command(BaseCommand):
    help = "Install M24 workflow and permission configuration; never grant access to users."

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
            activity_type_code="FACULTY_INTERNSHIP",
            defaults={
                "activity_type_name": "Industry / Faculty Internship",
                "activity_group": "INTERNSHIP",
            },
        )
        if kind.activity_group != "INTERNSHIP" or not kind.is_active:
            raise CommandError(
                "Existing FACULTY_INTERNSHIP configuration is incompatible; review it explicitly."
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
            module_code="FACULTY_INTERNSHIPS",
            defaults={"module_name": "Faculty Internships"},
        )
        resource, _ = iam.AccessResource.objects.get_or_create(
            access_module=module,
            resource_code="ACTIVITY",
            defaults={"resource_name": "Internship activity"},
        )
        count = 0
        for code, action in actions.items():
            _, created = iam.Permission.objects.get_or_create(
                permission_code=f"FACULTY_INTERNSHIPS.ACTIVITY.{code}",
                defaults={
                    "access_resource": resource,
                    "access_action": action,
                    "permission_name": f"Faculty internship {code.lower()}",
                },
            )
            count += created
        self.stdout.write(
            f"Created {count} permissions and installed required workflow defaults. No role or user grants changed."
        )
