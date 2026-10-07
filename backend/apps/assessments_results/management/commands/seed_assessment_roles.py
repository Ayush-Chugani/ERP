from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group,Permission
from django.db import transaction
class Command(BaseCommand):
    help='Prepare permission groups without assigning users or scope.'
    @transaction.atomic
    def handle(self,*args,**options):
        for name,actions in {'Faculty':['view','mark'],'Coordinator':['view','configure'],'Result cell':['view','calculate','export'],'Reviewer':['view','publish','correct']}.items():
            group,_=Group.objects.get_or_create(name='M10 '+name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label='assessments_results',codename__in=[a+'_assessment' for a in actions]))
        self.stdout.write('M10 groups prepared; no users assigned or modules activated.')
