from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group,Permission
from django.db import transaction
class Command(BaseCommand):
    help='Create M9 permission groups without assigning users or scopes.'
    @transaction.atomic
    def handle(self,*args,**options):
        roles={'Faculty':['view','manage','mark'],'Reviewer':['view','review','reopen'],'Coordinator':['view','manage','exceptional','export'],'Policy administrator':['view','configure']}
        for name,actions in roles.items():
            group,_=Group.objects.get_or_create(name='M9 '+name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label='attendance_lesson_plan',codename__in=[a+'_attendance' for a in actions]))
        self.stdout.write('M9 permission groups prepared; no user assignments or scope grants changed.')
