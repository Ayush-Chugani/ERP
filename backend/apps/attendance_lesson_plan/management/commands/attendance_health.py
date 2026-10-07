import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.attendance_lesson_plan import models as m
from apps.attendance_lesson_plan.selectors import reconcile,sessions
class Command(BaseCommand):
    help='Scoped reconciliation and backlog metrics; no mutations.'
    def add_arguments(self,p):p.add_argument('--actor',type=int,required=True)
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(pk=options['actor']);scope=sessions(actor)
        self.stdout.write(json.dumps({'findings':reconcile(actor),'pending_corrections':m.CorrectionRequest.objects.filter(attendance__class_session__in=scope,request_status='PENDING').count(),'undelivered_events':m.OutboxEvent.objects.filter(audit__section_id__in=scope.values('course_offering_section_id')).exclude(pk__in=m.Delivery.objects.values('event_id')).count()},default=str))
