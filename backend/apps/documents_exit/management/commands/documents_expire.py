import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.documents_exit import models as m
from apps.documents_exit import permissions as p
from apps.documents_exit import services as s


class Command(BaseCommand):
    help = "Scoped, explicit expiry sweep. Dry-run by default; never deletes files."

    def add_arguments(self, parser):
        parser.add_argument("--actor", type=int, required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--after", type=int, default=0)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options["actor"])
        if not p.can(actor, "verify_document"):
            raise CommandError("Enabled module and verifier capability required.")
        rows = list(
            p.scoped(m.StudentDocument, actor, "verify_document")
            .filter(
                pk__gt=options["after"],
                expiry_date__lt=timezone.localdate(),
                verification_status__in=["PENDING", "VERIFIED", "REJECTED"],
            )
            .order_by("pk")[: max(1, min(options["limit"], 500))]
        )
        done = failed = 0
        if options["apply"]:
            for row in rows:
                try:
                    s.verify_document(
                        actor=actor,
                        pk=row.pk,
                        expected_status=row.verification_status,
                        target="EXPIRED",
                        reason="Explicit expiry sweep",
                    )
                    done += 1
                except APIException:
                    failed += 1
        self.stdout.write(
            json.dumps(
                {
                    "dry_run": not options["apply"],
                    "eligible": len(rows),
                    "updated": done,
                    "failed": failed,
                    "next_after": rows[-1].pk if rows else None,
                }
            )
        )
