from django.core.management.base import BaseCommand
from apps.teaching_timetable.solver import run_next


class Command(BaseCommand):
    help = 'Run a bounded batch of queued timetable solver jobs outside web workers.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1)

    def handle(self, *args, **options):
        count = 0
        for _ in range(max(0, min(options['limit'], 100))):
            if not run_next():
                break
            count += 1
        self.stdout.write(f'Processed {count} timetable jobs.')
