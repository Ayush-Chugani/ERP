import json
from datetime import date
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.attendance_lesson_plan.commands import execute
from apps.attendance_lesson_plan.policies import require_section
from apps.teaching_timetable.models import PublishedOccurrence
class Command(BaseCommand):
    help='Generate bounded published sessions; dry-run by default. Requires explicit policy/calendar.'
    def add_arguments(self,p):
        p.add_argument('--actor',type=int,required=True);p.add_argument('--section',type=int,required=True)
        p.add_argument('--date-from',required=True);p.add_argument('--date-to',required=True);p.add_argument('--reason',required=True)
        p.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        start=date.fromisoformat(options['date_from']);end=date.fromisoformat(options['date_to'])
        if end<start or (end-start).days>31:raise CommandError('Use at most 31 days.')
        actor=get_user_model().objects.get(pk=options['actor']);section=require_section(actor,options['section'],'manage_attendance')
        rows=PublishedOccurrence.objects.filter(course_offering_section=section,revision__status='PUBLISHED',date__range=[start,end]).order_by('pk')
        if rows.count()>100:raise CommandError('Narrow the generation window to at most 100 occurrences.')
        results=[]
        with transaction.atomic():
            for row in rows:
                results.append(execute(actor=actor,operation='create-session',data={'section_id':section.pk,'occurrence_id':row.pk,'reason':options['reason']},key='generate-occurrence-'+str(row.pk)))
            if not options['apply']:transaction.set_rollback(True)
        self.stdout.write(json.dumps({'committed':options['apply'],'results':results}))
