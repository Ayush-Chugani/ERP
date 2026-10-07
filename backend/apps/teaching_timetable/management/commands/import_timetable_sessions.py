import csv
import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from apps.teaching_timetable import services as s
from apps.teaching_timetable.serializers import SessionValues


class Command(BaseCommand):
    help = 'Import mapped recurring sessions into a draft; dry-run unless --apply is supplied.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--actor', type=int, required=True)
        parser.add_argument('--revision', type=int, required=True)
        parser.add_argument('--version', type=int, required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--report', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        source = Path(options['csv_file'])
        if source.stat().st_size > 250000:
            raise CommandError('CSV exceeds 250 KB.')
        with source.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            required = set(SessionValues().fields) | {'source_id'}
            if set(reader.fieldnames or []) != required:
                raise CommandError('Required columns: ' + ', '.join(sorted(required)))
            rows = list(reader)
        if not 1 <= len(rows) <= 50:
            raise CommandError('Import 1 to 50 rows per batch.')
        parsed, quarantine, seen = [], [], set()
        for index, row in enumerate(rows, 2):
            source_id = row.pop('source_id', '')
            if not source_id or source_id in seen:
                quarantine.append({'line': index, 'error': 'Missing or duplicate source_id'})
                continue
            seen.add(source_id)
            for name in ('room_id', 'faculty_assignment_id'):
                row[name] = row.get(name) or None
            serializer = SessionValues(data=row)
            if not serializer.is_valid():
                quarantine.append({'line': index, 'error': serializer.errors})
            else:
                parsed.append((source_id, serializer.validated_data))
        actor = get_user_model().objects.get(pk=options['actor'])
        result = {'dry_run': not options['apply'], 'quarantine': quarantine}
        if not quarantine:
            @s.command
            def perform(*, actor):
                revision = s.revision_for(actor, options['revision'])
                def execute(current):
                    s.check_version(revision, options['version'])
                    mapping = []
                    with transaction.atomic():
                        for source_id, values in parsed:
                            obj = s.write_session(actor=current, revision_id=revision.pk,
                                expected_version=revision.version, values=values, reason=options['reason'])
                            mapping.append({'source_id': source_id, 'session_id': str(obj.pk) if options['apply'] else None})
                            revision.refresh_from_db()
                        if not options['apply']:
                            transaction.set_rollback(True)
                    return {'dry_run': not options['apply'], 'mapping': mapping}
                if not options['apply']:
                    return execute(actor)
                payload = {'revision': revision.pk, 'rows': parsed}
                return s.idempotent(actor=actor, key='session-import-' + s.digest(payload),
                    operation='session-import', payload=payload, execute=execute)
            from rest_framework.exceptions import APIException
            try:
                result = perform(actor=actor)
            except APIException as exc:
                result['quarantine'] = [{'error': exc.detail}]
        Path(options['report']).write_text(json.dumps(result, cls=DjangoJSONEncoder, indent=2), encoding='utf-8')
        self.stdout.write('Session import report written; publication is a separate command.')
