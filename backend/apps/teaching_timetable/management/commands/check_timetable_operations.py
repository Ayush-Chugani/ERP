import json
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from apps.teaching_timetable import models as m
from apps.teaching_timetable.engine import operational, check_collisions, SchedulingConflict


class Command(BaseCommand):
    help = 'Read-only M8 backlog, stalled-job and operational-collision checks.'

    def handle(self, *args, **options):
        stalled = m.SolverJob.objects.filter(status='RUNNING', started_at__lt=timezone.now()-timedelta(minutes=5)).count()
        failed = m.SolverJob.objects.filter(status='FAILED').count()
        conflict = False
        try:
            check_collisions(operational(), [])
        except SchedulingConflict:
            conflict = True
        metrics = {'stalled_jobs': stalled, 'failed_jobs': failed,
            'outbox_events': m.OutboxEvent.objects.count(),
            'consumer_receipts': m.EventReceipt.objects.count(), 'operational_conflict': conflict}
        self.stdout.write(json.dumps(metrics))
        if stalled or conflict:
            from django.core.management.base import CommandError
            raise CommandError('M8 requires operator attention; consult the rollout runbook.')
