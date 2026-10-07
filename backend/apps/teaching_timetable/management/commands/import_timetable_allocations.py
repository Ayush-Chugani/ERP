import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from apps.teaching_timetable.importing import parse_allocations
from apps.teaching_timetable.services import command, bulk_assignments, idempotent, digest
from apps.teaching_timetable.api import authorize


class Command(BaseCommand):
    help = 'Validate a mapped allocation CSV; dry-run by default, explicit --apply to commit.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--actor', type=int, required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report', required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options['actor'])
        source = Path(options['csv_file'])
        if source.stat().st_size > 250000:
            raise CommandError('CSV exceeds 250 KB.')
        rows, quarantine = parse_allocations(source.read_text(encoding='utf-8-sig'), options['reason'])
        if quarantine:
            result = {'applied': False, 'quarantine': quarantine}
        else:
            values = [row['values'] for row in rows]
            @command
            def perform(*, actor):
                for row in values:
                    authorize(actor, 'create-assignment', row)
                if not options['apply']:
                    return bulk_assignments(actor=actor, rows=values, dry_run=True, reason=options['reason'])
                return idempotent(actor=actor, key='allocation-import-' + digest(rows),
                    operation='allocation-import', payload=rows,
                    execute=lambda current: bulk_assignments(actor=current, rows=values,
                        dry_run=False, reason=options['reason']))
            result = perform(actor=actor)
            result['source_mapping'] = [{'source_id': row['source_id'], 'line': row['line']} for row in rows]
        Path(options['report']).write_text(json.dumps(result, cls=DjangoJSONEncoder, indent=2), encoding='utf-8')
        self.stdout.write('Import report written. ' + ('Apply requested.' if options['apply'] else 'Dry-run: no allocations retained.'))
