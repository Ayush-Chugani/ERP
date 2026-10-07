from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create M14 capability groups without user or institution assignments."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {
            "Communication author": [
                "create_announcement",
                "edit_announcement",
                "submit_announcement",
                "manage_attachments",
            ],
            "Communication approver": [
                "review_announcement",
                "approve_announcement",
                "reject_announcement",
                "archive_announcement",
                "view_audit",
            ],
            "Communication institution publisher": ["publish_institution"],
            "Communication type administrator": ["manage_types"],
        }
        for name, codes in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="communication", codename__in=codes
                )
            )
        self.stdout.write(
            "Four role groups reconciled. No user or scope assignments made. File sharing requires separate M13 authority."
        )
