import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework.exceptions import APIException
from apps.assessments_results import models as m,selectors as q,services as s
class Command(BaseCommand):
    help='Scoped exception counts and stale calculation diagnostics.'
    def add_arguments(self,p):p.add_argument('--actor',type=int,required=True)
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(pk=options['actor']);events=q.events(actor);results=q.course_results(actor)
        findings=[]
        for obj in results.filter(state='CALCULATED')[:1000]:
            try:
                _,current=s.course_inputs(obj.course_registration,obj.attempt_number,obj.policy)
                if current!={k:value for k,value in obj.evidence.items() if k!='calculated_by'}:findings.append({'id':obj.pk,'issue':'stale_calculation'})
            except (APIException,ValueError):findings.append({'id':obj.pk,'issue':'unresolved_inputs'})
        self.stdout.write(json.dumps({'unpublished_events':events.filter(status='CONDUCTED').count(),'withheld_results':results.filter(is_withheld=True).count(),'findings':findings},default=str))
