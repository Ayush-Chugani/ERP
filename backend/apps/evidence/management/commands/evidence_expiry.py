import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.evidence.tasks import expiry_notices


class Command(BaseCommand):
    help = "Scoped expiry reconciliation. Defaults to dry-run; configure a deduplicating adapter before delivery."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument(
            "--as-of", type=date.fromisoformat, default=timezone.localdate()
        )
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--after-id", type=int, default=0)

    def handle(self, *args, **options):
        self.stdout.write(
            json.dumps(
                expiry_notices(
                    actor=get_user_model().objects.get(pk=options["actor_id"]),
                    as_of=options["as_of"],
                    dry_run=not options["apply"],
                    limit=max(1, min(options["limit"], 1000)),
                    after_id=max(0, options["after_id"]),
                )
            )
        )
