"""Scoped reads and policy-grouped analytics; finalized evidence only."""
from collections import defaultdict
from django.db.models import Sum
from rest_framework.exceptions import NotFound,ValidationError
from . import models as m
from .policies import sections,require_session,own_student,enabled
from .calculations import summarize

def sessions(actor,action='view_attendance'):
    from .policies import scoped_sessions
    return scoped_sessions(actor,action).select_related('faculty_assignment','policy','course_offering_section__course_offering__course','course_offering_section__programme_term_offering__programme__department__campus')


def record(obj):
    from django.db import models
    out={'id':str(obj.pk)}
    for field in obj._meta.concrete_fields:
        if field.primary_key or isinstance(field,models.GeneratedField):continue
        value=getattr(obj,field.attname)
        out[field.attname]=str(value) if value is not None and field.is_relation else value
    return out

def register(actor,pk):
    obj=m.ClassSession.objects.select_related('policy','faculty_assignment','course_offering_section').get(pk=pk)
    require_session(actor,obj,'view_attendance')
    rows=m.StudentAttendance.objects.filter(class_session=obj).select_related('student','attendance_status').order_by('student__student_number','pk')
    return {'session':record(obj),'policy':record(obj.policy),'rows':[{**record(row),'student_number':row.student.student_number,'student_name':row.student.display_name,'status_code':row.attendance_status.status_code if row.attendance_status_id else None} for row in rows]}

def attendance_rows(actor,personal=False):
    if personal:
        return m.StudentAttendance.objects.filter(student_id=own_student(actor),class_session__register_status='FINALIZED').select_related('class_session__policy','attendance_status')
    return m.StudentAttendance.objects.filter(class_session__in=sessions(actor)).select_related('class_session__policy','attendance_status')

def report(actor,start,end,personal=False):
    if (end-start).days>366 or end<start:raise ValidationError('Use a report range up to 366 days.')
    rows=attendance_rows(actor,personal).filter(class_session__session_date__range=[start,end],class_session__register_status='FINALIZED',class_session__session_status='CONDUCTED')
    if rows.count()>20000:raise ValidationError('Narrow this report below 20,000 attendance rows.')
    groups=defaultdict(list);policies={}
    for row in rows:
        key=(row.student_id,row.class_session.course_offering_section_id,row.class_session.policy_id)
        groups[key].append({'credit':row.credit,'denominator':row.denominator});policies[row.class_session.policy_id]=row.class_session.policy
    return [{'student_id':str(student),'section_id':str(section),'policy_id':str(policy),**summarize(values,policies[policy].threshold)} for (student,section,policy),values in groups.items()]

def reconcile(actor):
    from .services import assert_roster,assert_schedule,Conflict
    findings=[]
    qs=sessions(actor)
    if qs.count()>1000:raise ValidationError("Reconciliation is limited to 1,000 sessions per scope.")
    for obj in qs:
        try:assert_schedule(obj)
        except Conflict:findings.append({'session_id':str(obj.pk),'issue':'timetable_changed'})
        if obj.register_status!='UNOPENED':
            try:assert_roster(obj)
            except Conflict:findings.append({'session_id':str(obj.pk),'issue':'roster_changed','finalized':obj.register_status=='FINALIZED'})
        if obj.session_status=='CONDUCTED' and obj.register_status!='FINALIZED':findings.append({'session_id':str(obj.pk),'issue':'unfinalized_register'})
    return findings[:1000]
