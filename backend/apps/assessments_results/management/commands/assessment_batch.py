import json
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.assessments_results.api.commands import execute_batch
class Command(BaseCommand):
    help='Validate explicitly mapped academic commands; dry-run unless --apply.'
    def add_arguments(self,p):
        p.add_argument('file');p.add_argument('--actor',type=int,required=True);p.add_argument('--key',required=True);p.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        path=Path(options['file'])
        if path.stat().st_size>1048576:raise CommandError('Maximum input is 1 MiB.')
        rows=json.loads(path.read_text(encoding='utf-8-sig'));actor=get_user_model().objects.get(pk=options['actor'])
        with transaction.atomic():
            results=execute_batch(actor=actor,rows=rows,key=options['key'])
            if not options['apply']:transaction.set_rollback(True)
        self.stdout.write(json.dumps({'committed':options['apply'],'results':results}))
