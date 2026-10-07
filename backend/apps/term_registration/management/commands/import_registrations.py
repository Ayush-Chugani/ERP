import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from rest_framework.exceptions import APIException
from apps.term_registration.operations import parse_csv
from apps.term_registration.execution import bulk


class Command(BaseCommand):
    help='Preview mapped registration CSV commands; --apply commits one atomic batch.'
    def add_arguments(self,parser):
        parser.add_argument('file');parser.add_argument('--actor',required=True,type=int)
        parser.add_argument('--key',required=True);parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        path=Path(options['file'])
        if path.stat().st_size>1_000_000: raise CommandError('Import is limited to 1 MB.')
        try:
            result=bulk(actor=get_user_model().objects.get(pk=options['actor']),rows=parse_csv(path.read_text(encoding='utf-8-sig')),key=options['key'],dry_run=not options['apply'])
        except APIException as exc: raise CommandError(json.dumps(exc.detail)) from None
        self.stdout.write(json.dumps({'applied':options['apply'],'results':result}))
