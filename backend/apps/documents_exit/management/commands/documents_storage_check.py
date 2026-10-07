import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.documents_exit import models as m
from apps.documents_exit import storage


class Command(BaseCommand):
    help = "Read-only bounded registry/storage reconciliation; never purges retained evidence."

    def add_arguments(self, parser):
        parser.add_argument("--actor", type=int, required=True)
        parser.add_argument("--after", type=int, default=0)
        parser.add_argument("--scan-orphans", action="store_true")
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options["actor"])
        if not actor.is_active or not actor.is_superuser:
            raise CommandError(
                "Global registry checks require a platform administrator."
            )
        rows = list(
            m.FileObject.objects.filter(pk__gt=options["after"]).order_by("pk")[
                : max(1, min(options["limit"], 500))
            ]
        )
        backend = storage.backend()
        missing = sum(
            1
            for row in rows
            if row.storage_provider != backend.provider
            or not backend.exists(row.storage_key)
        )
        orphan_count = None
        truncated = False
        if options["scan_orphans"]:
            from itertools import islice

            if not hasattr(backend, "keys"):
                raise CommandError("This backend does not support key enumeration.")
            limit = max(1, min(options["limit"], 500))
            keys = list(islice(backend.keys(), limit + 1))
            truncated = len(keys) > limit
            keys = keys[:limit]
            known = set(
                m.FileObject.objects.filter(
                    storage_provider=backend.provider, storage_key__in=keys
                ).values_list("storage_key", flat=True)
            )
            orphan_count = sum(key not in known for key in keys)
        self.stdout.write(
            json.dumps(
                {
                    "examined": len(rows),
                    "missing_or_wrong_provider": missing,
                    "soft_deleted": sum(row.deleted_at is not None for row in rows),
                    "next_after": rows[-1].pk if rows else None,
                    "purge_enabled": False,
                    "unregistered_objects_in_sample": orphan_count,
                    "object_scan_truncated": truncated,
                }
            )
        )
