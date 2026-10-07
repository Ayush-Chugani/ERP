import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.student_support import permissions as p


class Command(BaseCommand):
    help = "Metadata-only support counts scoped to an approved operator."

    def add_arguments(self, parser):
        parser.add_argument("--actor", type=int, required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options["actor"])
        if not p.can(actor, "view_grievance_reports"):
            raise CommandError("Report capability and enabled module required.")
        grievances = p.grievances(actor, "view_grievance_reports")
        sessions = p.sessions(actor)
        self.stdout.write(
            json.dumps(
                {
                    "unresolved_grievances": grievances.filter(
                        status__in=["SUBMITTED", "ASSIGNED", "UNDER_REVIEW"]
                    ).count(),
                    "followups_due": sessions.filter(
                        session_status="FOLLOW_UP_REQUIRED",
                        follow_up_date__lte=timezone.localdate(),
                    ).count(),
                    "sla_configured": False,
                }
            )
        )
