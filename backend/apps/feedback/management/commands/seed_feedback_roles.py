from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group,Permission
from django.db import transaction
class Command(BaseCommand):
    help='Prepare feedback capability groups without assigning users or scopes.'
    @transaction.atomic
    def handle(self,*args,**options):
        roles={'Respondent':['submit_feedback'],'Faculty':['view_faculty_results'],'Coordinator':['manage_cycles','view_admin_results','export_results'],'Administrator':['manage_question_bank','manage_questionnaires','manage_cycles','view_admin_results','export_results'],'Text reviewer':['view_admin_results','view_text_feedback']}
        for name,permissions in roles.items():
            group,_=Group.objects.get_or_create(name='M11 '+name);group.permissions.add(*Permission.objects.filter(content_type__app_label='feedback',codename__in=permissions))
        self.stdout.write('M11 groups prepared; no users assigned or modules activated.')
