"""Restartable, explicitly mapped commands. Dry-run rolls back the entire batch."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import APIException
from apps.attendance_lesson_plan.commands import execute

class Command(BaseCommand):
    help='Validate/import up to 100 explicitly mapped attendance commands; dry-run by default.'
    def add_arguments(self,p):
        p.add_argument('file');p.add_argument('--actor',type=int,required=True);p.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        path=Path(options['file'])
        if path.stat().st_size>1048576:raise CommandError('Maximum input size is 1 MiB.')
        rows=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(rows,list) or not 1<=len(rows)<=100:raise CommandError('Use a list of 1-100 mapped commands.')
        actor=get_user_model().objects.get(pk=options['actor']);report=[]
        with transaction.atomic():
            for index,row in enumerate(rows):
                try:
                    if not isinstance(row,dict) or set(row)!={'operation','data','key'}:raise ValueError('Expected operation, data and stable source key.')
                    with transaction.atomic():result=execute(actor=actor,operation=row['operation'],data=row['data'],key=row['key'])
                    report.append({'row':index+1,'status':'valid','result':result})
                except (APIException,ValueError,KeyError) as exc:
                    report.append({'row':index+1,'status':'quarantined','error':str(exc)})
            failed=any(r['status']=='quarantined' for r in report)
            if not options['apply'] or failed:transaction.set_rollback(True)
        self.stdout.write(json.dumps({'committed':options['apply'] and not failed,'rows':report},default=str))
        if failed:raise CommandError('Batch rolled back; correct quarantined mappings and retry using the same keys.')
