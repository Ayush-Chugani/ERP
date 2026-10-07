import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.feedback import permissions as p
from apps.feedback.api.commands import execute
from rest_framework.exceptions import APIException
class Command(BaseCommand):
    help='Explicit scheduled transitions using a scoped operator; no read-triggered transitions.'
    def add_arguments(self,p):p.add_argument('--actor',type=int,required=True)
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(pk=options['actor']);now=timezone.now();report=[]
        for obj in p.cycles(actor).filter(status__in=['SCHEDULED','OPEN']).order_by('pk')[:500]:
            action='close' if obj.status=='OPEN' and now>=obj.end_at else 'cancel' if obj.status=='SCHEDULED' and now>=obj.end_at else 'open' if obj.status=='SCHEDULED' and obj.start_at<=now<obj.end_at else None
            if not action:continue
            try:
                result=execute(actor=actor,operation='cycle-action',data={'pk':obj.pk,'expected_version':obj.version,'action':action,'reason':'Scheduled cycle transition'},key=f'tick:{obj.pk}:{obj.version}:{action}')
                report.append({'cycle':obj.pk,'action':action,'status':'done'})
            except APIException as error:report.append({'cycle':obj.pk,'status':'failed','code':error.status_code})
        self.stdout.write(json.dumps(report))
