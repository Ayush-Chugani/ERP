import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.documents_exit import models as m
from apps.documents_exit import permissions as p


class Command(BaseCommand):
    help = "Scoped aged-request counts using an operator-supplied age; not an invented SLA."

    def add_arguments(self, parser):
        parser.add_argument("--actor", type=int, required=True)
        parser.add_argument("--older-than-days", type=int, required=True)

    def handle(self, *args, **options):
        if options["older_than_days"] < 1:
            raise CommandError("A positive age is required.")
        actor = get_user_model().objects.get(pk=options["actor"])
        if not p.can(actor, "view_certificates"):
            raise CommandError(
                "Enabled module and certificate read permission required."
            )
        count = (
            p.scoped(m.CertificateRequest, actor, "view_certificates")
            .filter(
                request_status__in=["SUBMITTED", "UNDER_REVIEW", "APPROVED"],
                requested_at__lt=timezone.now()
                - timedelta(days=options["older_than_days"]),
            )
            .count()
        )
        self.stdout.write(
            json.dumps(
                {
                    "aged_active_requests": count,
                    "older_than_days": options["older_than_days"],
                    "sla_classification": False,
                }
            )
        )
