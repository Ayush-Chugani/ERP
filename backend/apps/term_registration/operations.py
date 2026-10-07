"""Read-only anomaly report and deterministic legacy import parsing."""
import csv
import io
import json
from .selectors import scoped
from . import models as m
from .policies import SEAT_STATUSES


def reconcile(actor,action='manage_registration'):
    findings=[]
    for resource,relation in [('sections','class_section'),('batches','class_batch')]:
        for row in scoped(actor,resource,action):
            occupied=m.StudentTermRegistration.objects.filter(**{relation:row},registration_status__in=SEAT_STATUSES).count()
            if row.capacity is not None and occupied>row.capacity:
                findings.append({'resource':resource,'id':str(row.pk),'issue':'over_capacity','occupied':occupied,'capacity':row.capacity})
    for row in scoped(actor,'courses',action):
        occupied=m.StudentCourseRegistration.objects.filter(course_offering=row,registration_status__in=SEAT_STATUSES).count()
        if row.registration_capacity is not None and occupied>row.registration_capacity:
            findings.append({'resource':'courses','id':str(row.pk),'issue':'over_capacity'})
    for row in scoped(actor,'registrations',action).filter(registration_status='APPROVED'):
        required=set(m.CourseOfferingSection.objects.filter(course_offering=row.course_offering,class_section=row.term_registration.class_section).values_list('session_type',flat=True))
        actual=set(m.CourseOfferingSectionStudent.objects.filter(course_registration=row,roster_status='ACTIVE').values_list('session_type',flat=True))
        if required-actual: findings.append({'resource':'registrations','id':str(row.pk),'issue':'missing_roster','session_types':sorted(required-actual)})
    for row in scoped(actor,'rosters',action).filter(roster_status='ACTIVE').exclude(course_registration__registration_status='APPROVED'):
        findings.append({'resource':'rosters','id':str(row.pk),'issue':'inactive_registration'})
    return {'findings':findings[:1000],'count':len(findings),'truncated':len(findings)>1000}


def parse_csv(content):
    from rest_framework.exceptions import ValidationError
    if len(content)>1_000_000: raise ValidationError('Import is limited to 1 MB.')
    reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    if reader.fieldnames != ['operation','data']:
        raise ValidationError('CSV header must be operation,data; data is a JSON object of mapped identifiers.')
    rows=[]
    for index,row in enumerate(reader,2):
        try:
            if None in row: raise ValueError()
            data=json.loads(row['data'])
            if not isinstance(data,dict): raise ValueError()
        except (ValueError,TypeError): raise ValidationError({'row':index,'detail':'Invalid JSON data object.'})
        rows.append({'operation':row['operation'],'data':data})
        if len(rows)>100: raise ValidationError('Import is limited to 100 rows.')
    if not rows: raise ValidationError('No import rows.')
    return rows
