from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.identity_access.models import UserRoleAssignment,RoleDelegation
from apps.identity_access.audit import record

class Command(BaseCommand):
    help='Preview expired assignments/delegations; --apply records their expiry without deleting history.'
    def add_arguments(self,parser): parser.add_argument('--apply',action='store_true')
    @transaction.atomic
    def handle(self,*args,**options):
        now=timezone.now();counts={}
        for model,status in ((UserRoleAssignment,'assignment_status'),(RoleDelegation,'delegation_status')):
            rows=model.objects.select_for_update().filter(valid_to__lte=now,**{status+'__in':['PENDING','ACTIVE']})
            counts[model._meta.db_table]=rows.count()
            if options['apply']:
                for row in rows:
                    old=getattr(row,status);setattr(row,status,'EXPIRED');row.save(update_fields=[status])
                    record(actor=None,action='UPDATE',entity=row,before={'status':old},after={'status':'EXPIRED'},details={'event':'scheduled_expiry'})
        self.stdout.write(('Applied: ' if options['apply'] else 'Dry run: ')+str(counts))
