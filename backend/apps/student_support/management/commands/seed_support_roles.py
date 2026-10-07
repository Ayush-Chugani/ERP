from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.student_support.policies import CAPABILITIES


class Command(BaseCommand):
    help = "Create capability groups only; does not assign users, scopes or categories."

    def handle(self, *args, **options):
        roles = {
            "Support Student": [
                "submit_own_grievance",
                "view_own_grievance",
                "view_counselling_normal",
            ],
            "Support Mentor": [
                "conduct_counselling",
                "view_counselling_normal",
                "view_counselling_restricted",
            ],
            "Support Grievance Officer": [
                "view_grievance_queue",
                "triage_grievance",
                "resolve_grievance",
                "close_grievance",
                "view_grievance_reports",
            ],
            "Support Administrator": list(CAPABILITIES),
        }
        for name, caps in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="student_support", codename__in=caps
                )
            )
        self.stdout.write(
            "Support capability groups ready; no users or institutional categories seeded."
        )
