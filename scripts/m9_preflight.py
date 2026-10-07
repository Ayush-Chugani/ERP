"""Read-only M9 prerequisite schema capture; invoke through manage.py shell."""
from pathlib import Path
from django.db import connection
from django.contrib.auth import get_user_model
from apps.term_registration.models import CourseOfferingSection, CourseOfferingSectionStudent
from apps.teaching_timetable.models import FacultyAssignment, TimetableSession, PublishedOccurrence
from apps.organization.models import Room

models=[get_user_model(),CourseOfferingSection,CourseOfferingSectionStudent,FacultyAssignment,TimetableSession,PublishedOccurrence,Room]
lines=['# M9 upstream schema preflight','', 'Read-only metadata snapshot; contains no student or employee records.','']
with connection.cursor() as cursor:
    for model in models:
        table=model._meta.db_table
        cursor.execute('SHOW CREATE TABLE '+connection.ops.quote_name(table))
        definition=cursor.fetchone()[1]
        lines.extend(['## '+table,'',definition,''])
Path('Manuals/M9_UPSTREAM_SCHEMA.md').write_text('\n'.join(lines),encoding='utf-8')
print('Recorded prerequisite table definitions for',len(models),'models.')
