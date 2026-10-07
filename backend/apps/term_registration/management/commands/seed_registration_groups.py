from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help='Create additive M7 permission groups; assigns no users, scopes or activation flags.'
    def handle(self,*args,**options):
        groups={
            'M7 Registrar':['view_registration','manage_registration','approve_registration','approve_progression','export_registration'],
            'M7 Coordinator':['view_registration','manage_registration'],
            'M7 Policy Administrator':['view_registration','configure_registration','authorize_special_course'],
            'M7 Reader':['view_registration'],
        }
        for name,codes in groups.items():
            group,_=Group.objects.get_or_create(name=name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label='term_registration',codename__in=codes))
            self.stdout.write(name)
