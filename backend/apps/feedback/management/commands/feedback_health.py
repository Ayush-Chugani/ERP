import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.feedback import permissions as p,models as m
class Command(BaseCommand):
    help='Scoped feedback scheduler diagnostics; no response identities or answers.'
    def add_arguments(self,p):p.add_argument('--actor',type=int,required=True)
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(pk=options['actor']);qs=p.cycles(actor);now=timezone.now()
        self.stdout.write(json.dumps({'due_to_open':qs.filter(status='SCHEDULED',start_at__lte=now,end_at__gt=now).count(),'overdue_to_close':qs.filter(status='OPEN',end_at__lte=now).count(),'expired_scheduled':qs.filter(status='SCHEDULED',end_at__lte=now).count()}))
