import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, F
from django.utils import timezone

from apps.communication import permissions as p


class Command(BaseCommand):
    help = "Read-only scoped counts; no publication mutation, notifications or purge."

    def add_arguments(self, parser):
        parser.add_argument("--actor", type=int, required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options["actor"])
        rows = p.management(actor, "view_audit")
        now = timezone.now()
        report = {
            "total": rows.count(),
            "status": list(rows.values("approval_status").annotate(count=Count("pk"))),
            "audience": list(rows.values("audience_type").annotate(count=Count("pk"))),
            "invalid_windows": rows.filter(publish_to__lte=F("publish_from")).count(),
            "expired_approved": rows.filter(
                approval_status="APPROVED", publish_to__lte=now
            ).count(),
            "scheduled": rows.filter(
                approval_status="APPROVED", publish_from__gt=now
            ).count(),
            "attachments": rows.aggregate(count=Count("attachments"))["count"],
            "missing_programme_targets": rows.filter(
                audience_type="PROGRAMME", programme_targets__isnull=True
            ).count(),
            "missing_custom_targets": rows.filter(
                audience_type="CUSTOM", user_targets__isnull=True
            ).count(),
        }
        self.stdout.write(json.dumps(report))
