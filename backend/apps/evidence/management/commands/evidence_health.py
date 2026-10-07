import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.documents_exit.storage import backend


class Command(BaseCommand):
    help = "Read-only evidence integrity/configuration check; does not send notifications or expose storage keys."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM evidence_document d WHERE (SELECT COUNT(*) FROM evidence_document_version v WHERE v.evidence_document_id=d.evidence_document_id AND v.is_current=1 AND v.version_number=d.current_version_number) <> 1"
            )
            invalid = cursor.fetchone()[0]
        output = {
            "runtime_enabled": settings.EVIDENCE_ENABLED,
            "current_version_invariant_failures": invalid,
            "scanner_configured": bool(settings.DOCUMENTS_MALWARE_SCANNER),
            "storage_provider": backend().provider,
            "notification_adapter_configured": bool(
                settings.EVIDENCE_NOTIFICATION_HANDLER
            ),
        }
        self.stdout.write(json.dumps(output))
        if invalid:
            raise CommandError(
                "Current-version integrity requires administrator review."
            )
