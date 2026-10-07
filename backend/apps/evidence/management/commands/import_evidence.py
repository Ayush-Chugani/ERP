import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.evidence.imports import legacy_import


class Command(BaseCommand):
    help = "Validate or import up to 200 legacy evidence rows; default dry-run, per-row durable transactions."

    def add_arguments(self, parser):
        for name in ("manifest", "root", "namespace"):
            parser.add_argument("--" + name, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["manifest"])
        if path.stat().st_size > 262144:
            raise CommandError("Manifest exceeds 256 KiB.")
        result = legacy_import(
            actor=get_user_model().objects.get(pk=options["actor_id"]),
            entries=json.loads(path.read_text(encoding="utf-8-sig")),
            root=options["root"],
            namespace=options["namespace"],
            dry_run=not options["apply"],
        )
        self.stdout.write(json.dumps(result))
        if result["failed"]:
            raise CommandError(
                "Some rows require mapping/file review; rerun with the same namespace/source IDs after correction."
            )
