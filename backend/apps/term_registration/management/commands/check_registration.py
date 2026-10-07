import json
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.term_registration.operations import reconcile


class Command(BaseCommand):
    help='Report scoped registration capacity and roster anomalies without modifying records.'
    def add_arguments(self,parser): parser.add_argument('--actor',required=True,type=int)
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(pk=options['actor'])
        from apps.term_registration.policies import permitted
        if not permitted(actor,'manage_registration'): raise CommandError('Registration authority unavailable.')
        report=reconcile(actor)
        self.stdout.write(json.dumps(report))
        if report['count']: raise CommandError('Registration reconciliation found anomalies.')
