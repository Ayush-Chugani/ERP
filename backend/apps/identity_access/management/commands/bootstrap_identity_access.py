from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.identity_access.models import Role,UserRoleAssignment
from apps.identity_access.audit import record

class Command(BaseCommand):
    help='Preview or explicitly bootstrap the first M15 recovery administrator. No automatic user selection.'
    def add_arguments(self,parser):
        parser.add_argument('--user-id',type=int,required=True)
        parser.add_argument('--operator-id',type=int,required=True)
        parser.add_argument('--reason',required=True)
        parser.add_argument('--apply',action='store_true')
    @transaction.atomic
    def handle(self,*args,**options):
        users=get_user_model().objects.select_for_update()
        operator=users.filter(pk=options['operator_id'],is_active=True,is_superuser=True).first()
        target=users.filter(pk=options['user_id'],is_active=True,account_status='ACTIVE').first()
        if not operator or not target or not options['reason'].strip() or len(options['reason'])>500:
            raise CommandError('Active existing platform operator, active target and bounded reason required.')
        if UserRoleAssignment.objects.filter(role__role_code='SUPER_ADMIN',assignment_status='ACTIVE').exists():
            raise CommandError('An active recovery assignment already exists; use the audited administration workflow.')
        role=Role.objects.filter(role_code='SUPER_ADMIN',is_active=True).first()
        if not role: raise CommandError('Install the M15 source catalogue first.')
        if not options['apply']:
            self.stdout.write('Dry run: would assign SUPER_ADMIN at GLOBAL scope to the explicitly selected user. No changes made.')
            return
        row=UserRoleAssignment.objects.create(user=target,role=role,scope_type='GLOBAL',valid_from=timezone.now(),assigned_by_user=operator,assignment_reason=options['reason'])
        record(actor=operator,action='ASSIGN',entity=row,details={'event':'bootstrap','target_user_id':target.pk,'reason':options['reason']})
        self.stdout.write('Recovery assignment created; feature flags remain unchanged.')
