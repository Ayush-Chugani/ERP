from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity_access import models as m


class Command(BaseCommand):
    help = (
        "Create the M22 permission catalogue without granting roles or assigning users."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        actions = {
            a.action_code: a
            for a in m.AccessAction.objects.filter(
                action_code__in=[
                    "READ",
                    "CREATE",
                    "UPDATE",
                    "DELETE",
                    "VERIFY",
                    "EXPORT",
                ]
            )
        }
        if len(actions) != 6:
            raise CommandError("Install the M15 action catalogue first.")
        module, _ = m.AccessModule.objects.get_or_create(
            module_code="CONFERENCES", defaults={"module_name": "Conferences"}
        )
        count = 0
        for code, verbs in {
            "EVENT": ("READ", "CREATE", "UPDATE"),
            "ACTIVITY": ("READ", "CREATE", "UPDATE", "DELETE", "VERIFY", "EXPORT"),
        }.items():
            resource, _ = m.AccessResource.objects.get_or_create(
                access_module=module,
                resource_code=code,
                defaults={"resource_name": code.title()},
            )
            for verb in verbs:
                _, created = m.Permission.objects.get_or_create(
                    permission_code=f"CONFERENCES.{code}.{verb}",
                    defaults={
                        "access_resource": resource,
                        "access_action": actions[verb],
                        "permission_name": f"Conference {code.lower()} {verb.lower()}",
                    },
                )
                count += created
        self.stdout.write(
            f"Created {count} permissions. No roles or user assignments changed."
        )
