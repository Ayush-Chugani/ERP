"""All writes lock shared governance before current authorization and aggregate state."""
from contextvars import ContextVar
from functools import wraps
from datetime import datetime
from decimal import Decimal
import hashlib,json,logging
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelError,ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction,IntegrityError,OperationalError,models
from django.db.models import Max,Q
from django.utils import timezone
from rest_framework.exceptions import APIException,ValidationError,NotFound,PermissionDenied
from . import models as m
from .policies import require_section,require_session,own_student,grants
from .calculations import validate_rules,contribution
request_key=ContextVar('attendance_request_key',default='internal')
logger=logging.getLogger(__name__)

class Conflict(APIException):
    status_code=409
    default_code='attendance_conflict'
    default_detail='Attendance conflicts with current state.'

def command(fn):
    @wraps(fn)
    def run(*,actor,**kwargs):
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='organization',model='university')
                actor=get_user_model().objects.get(pk=actor.pk)
                return fn(actor=actor,**kwargs)
        except (IntegrityError,OperationalError) as exc:
            if exc.args and exc.args[0] in (1062,1451,1452,3819,4025,1205,1213):raise Conflict('Constraint or concurrent update conflict; refresh and retry.') from None
            raise
        except ModelError as exc:raise ValidationError(getattr(exc,'message_dict',exc.messages)) from None
        except ObjectDoesNotExist:raise NotFound('Attendance resource unavailable.') from None
    return run

def reason(value):
    if not isinstance(value,str) or not value.strip() or len(value)>1000:raise ValidationError('Supply a nonblank reason up to 1000 characters.')

def save(obj):
    obj.full_clean(exclude=[f.name for f in obj._meta.fields if isinstance(f,models.GeneratedField)])
    obj.save();return obj

def snapshot(obj):
    return {f.attname: str(getattr(obj,f.attname)) if getattr(obj,f.attname) is not None else None for f in obj._meta.concrete_fields if not isinstance(f,models.GeneratedField)}

def audit(obj,actor,section,action,why,before=None):
    authority={'superuser':actor.is_superuser,'grants':list(grants(actor).filter(membership__institution_id=section.programme_term_offering.programme.department.campus.institution_id).values('id','role','campus_id','department_id'))}
    event=m.AuditEvent.objects.create(section=section,actor=actor,authority=authority,action=action,resource=obj._meta.model_name,record_id=obj.pk,reason=why,request_key=request_key.get(),before=before or {},after=snapshot(obj))
    m.OutboxEvent.objects.create(audit=event,topic='attendance.'+action+'.v1',payload={'audit_id':str(event.pk),'section_id':str(section.pk),'record_id':str(obj.pk),'resource':obj._meta.model_name})
    return event

def version(obj,expected):
    if str(obj.version)!=str(expected):raise Conflict('Stale version. Refresh before applying changes.')

def session_for(actor,pk,action):
    obj=m.ClassSession.objects.select_for_update().select_related('policy','faculty_assignment','course_offering_section__programme_term_offering__programme__department__campus').get(pk=pk)
    require_session(actor,obj,action);return obj

def update_session(obj,actor,why,action,before):
    obj.version+=1;obj.updated_by=actor;save(obj);audit(obj,actor,obj.course_offering_section,action,why,before);return obj

def current_roster(obj):
    from apps.term_registration.models import CourseOfferingSectionStudent
    return CourseOfferingSectionStudent.objects.filter(course_offering_section_id=obj.course_offering_section_id,effective_from__lte=obj.session_date).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=obj.session_date)).select_related('course_registration__term_registration__enrolment')

def assert_roster(obj):
    actual=set(current_roster(obj).values_list('pk',flat=True))
    frozen=set(m.StudentAttendance.objects.filter(class_session=obj,is_eligible=True).values_list('course_offering_section_student_id',flat=True))
    if actual!=frozen:raise Conflict('Dated roster changed. Resolve it explicitly before finalization; existing marks were preserved.')

def end_has_passed(obj):
    from django.conf import settings
    from zoneinfo import ZoneInfo
    campus=obj.course_offering_section.programme_term_offering.programme.department.campus_id
    zone=ZoneInfo(getattr(settings,'CALENDAR_CAMPUS_TIMEZONES',{}).get(str(campus),settings.TIME_ZONE))
    if datetime.combine(obj.session_date,obj.end_time,tzinfo=zone)>timezone.now():
        raise Conflict('The scheduled class has not ended.')

def edit_window(obj):
    if (timezone.localdate()-obj.session_date).days>obj.policy.edit_days and obj.register_status!='REOPENED':
        raise Conflict('Ordinary edit window has closed; authorized reopening is required.')

@command
def configure_policy(*,actor,section_id,expected_number,basis,rules,threshold,edit_days,correction_days,reason):
    globals()['reason'](reason);section=require_section(actor,section_id,'configure_attendance')
    latest=m.PolicyRevision.objects.filter(section=section).aggregate(n=Max('number'))['n'] or 0
    if latest!=expected_number:raise Conflict('Stale policy revision.')
    try:validate_rules(rules)
    except ValueError as exc:raise ValidationError(str(exc))
    if set(rules)-set(m.AttendanceStatus.objects.filter(is_active=True).values_list('status_code',flat=True)):raise ValidationError('Unknown attendance status code.')
    obj=save(m.PolicyRevision(section=section,number=latest+1,basis=basis,rules=rules,threshold=threshold,edit_days=edit_days,correction_days=correction_days,actor=actor,reason=reason))
    audit(obj,actor,section,'policy_created',reason);return obj

def resolved_occurrence(pk):
    from apps.teaching_timetable import models as t
    from apps.teaching_timetable.engine import operational
    source=t.PublishedOccurrence.objects.select_related('session','revision').get(pk=pk)
    if source.revision.status!='PUBLISHED':raise Conflict('Occurrence is no longer published.')
    changes=t.OccurrenceException.objects.filter(occurrence=source).order_by('-sequence').first()
    day=changes.date if changes else source.date
    row=next((r for r in operational(date_from=day,date_to=day) if r.identity==source.pk),None)
    if row is None:raise Conflict('Occurrence was cancelled or withdrawn.')
    return source,row,changes

def assert_schedule(obj):
    if not obj.occurrence_id:return
    _,row,change=resolved_occurrence(obj.occurrence_id)
    if (row.day,row.start,row.end,row.room_id,row.employee_id,change.sequence if change else 0)!=(obj.session_date,obj.start_time,obj.end_time,obj.room_id,obj.faculty_assignment.employee_id,obj.occurrence_sequence):
        raise Conflict('Published timetable changed. Reconcile the session; attendance was not rewritten.')

def validate_session(obj,actor,source_occurrence=None):
    from .integrations import calendar_evidence
    from apps.teaching_timetable.engine import validate_assignment,Occurrence,operational,check_collisions,require_availability
    from apps.teaching_timetable.engine import scope
    section=obj.course_offering_section;term=section.programme_term_offering.academic_term
    if not term.start_date<=obj.session_date<=term.end_date or obj.start_time>=obj.end_time:raise ValidationError('Session must fit the academic term and a positive same-day interval.')
    assignment=obj.faculty_assignment
    if assignment.course_offering_section_id!=section.pk or assignment.assignment_status not in ('ACTIVE','COMPLETED') or not assignment.start_date<=obj.session_date<=(assignment.end_date or term.end_date):raise ValidationError('Faculty assignment does not cover this section and date.')
    validate_assignment(assignment,active=True)
    room=obj.room
    if not room.is_active or not room.building.is_active or room.building.campus_id!=scope(section).pk:raise ValidationError('Room must be active on the section campus.')
    if section.session_type=='PRACTICAL' and room.room_type!='LAB':raise ValidationError('Practical sessions require a laboratory.')
    obj.calendar_reference=calendar_evidence(section,obj.session_date)
    students=frozenset(r.course_registration.term_registration.enrolment.student_id for r in current_roster(obj))
    if room.capacity is None or len(students)>room.capacity:raise Conflict('Set sufficient room capacity.')
    proposed=Occurrence(None,0,section.pk,section.class_section_id,section.class_batch_id,assignment.employee_id,room.pk,obj.session_date,obj.start_time,obj.end_time,students)
    require_availability(proposed,scope(section).institution_id)
    existing=[row for row in operational(date_from=obj.session_date,date_to=obj.session_date) if row.identity!=source_occurrence]
    # Published sessions are already validated by M8; exceptional M9 sessions must not collide.
    if source_occurrence is None:check_collisions([proposed],existing)
    for other in m.ClassSession.objects.filter(session_date=obj.session_date,session_status__in=['PLANNED','CONDUCTED']).exclude(pk=obj.pk):
        if other.occurrence_id==source_occurrence and source_occurrence is not None:continue
        if obj.start_time<other.end_time and other.start_time<obj.end_time and (obj.room_id==other.room_id or assignment.employee_id==other.faculty_assignment.employee_id or section.class_section_id==other.course_offering_section.class_section_id):
            raise Conflict('Class session overlaps an existing room, instructor or class session.')

@command
def create_session(*,actor,section_id,reason,occurrence_id=None,faculty_assignment_id=None,room_id=None,session_date=None,start_time=None,end_time=None,source_session_id=None):
    globals()['reason'](reason)
    section=require_section(actor,section_id,'manage_attendance' if occurrence_id else 'exceptional_attendance',session_date)
    policy=m.PolicyRevision.objects.filter(section=section).order_by('-number').first()
    if not policy:raise Conflict('Configure this section attendance policy first.')
    sequence=0;timetable_id=None
    if occurrence_id:
        source,row,change=resolved_occurrence(occurrence_id)
        if row.section_id!=section.pk:raise ValidationError('Occurrence belongs to another section.')
        existing=m.ClassSession.objects.filter(occurrence=source).first()
        if existing:
            require_session(actor,existing,'manage_attendance');assert_schedule(existing);return existing
        faculty_assignment_id=change.faculty_assignment_id if change else source.session.faculty_assignment_id
        session_date,start_time,end_time,room_id=row.day,row.start,row.end,row.room_id
        sequence=change.sequence if change else 0;timetable_id=source.session_id
    require_section(actor,section.pk,'manage_attendance' if occurrence_id else 'exceptional_attendance',session_date)
    number=(m.ClassSession.objects.filter(course_offering_section=section).aggregate(n=Max('class_number'))['n'] or 0)+1
    obj=m.ClassSession(course_offering_section=section,faculty_assignment_id=faculty_assignment_id,room_id=room_id,session_date=session_date,start_time=start_time,end_time=end_time,session_type=section.session_type,class_number=number,policy=policy,created_by=actor,updated_by=actor,occurrence_id=occurrence_id,timetable_session_id=timetable_id,occurrence_sequence=sequence,source_session_id=source_session_id)
    if source_session_id:
        old=session_for(actor,source_session_id,'exceptional_attendance')
        if old.course_offering_section_id!=section.pk or old.register_status!='UNOPENED' or old.session_status!='PLANNED':raise Conflict('Only an unopened planned session can be replaced.')
        before=snapshot(old);old.session_status='RESCHEDULED';update_session(old,actor,reason,'session_rescheduled',before)
    require_session(actor,obj,'manage_attendance' if occurrence_id else 'exceptional_attendance')
    validate_session(obj,actor,occurrence_id);save(obj);audit(obj,actor,section,'session_created',reason);return obj

@command
def transition_session(*,actor,session_id,expected_version,action,reason):
    globals()['reason'](reason)
    permission='reopen_attendance' if action=='reopen' else 'mark_attendance' if action in ['mark','finalize','open','conduct'] else 'manage_attendance'
    obj=session_for(actor,session_id,permission);version(obj,expected_version);before=snapshot(obj)
    if action=='cancel':
        if obj.register_status!='UNOPENED' or obj.session_status!='PLANNED':raise Conflict('Only an unopened planned session may be cancelled.')
        obj.session_status='CANCELLED'
    elif action=='conduct':
        if obj.session_status!='PLANNED':raise Conflict('Only a planned session may be conducted.')
        end_has_passed(obj);assert_schedule(obj);obj.session_status='CONDUCTED'
    elif action=='open':
        if obj.session_status!='CONDUCTED' or obj.register_status!='UNOPENED':raise Conflict('Conduct the session before opening a register.')
        end_has_passed(obj);assert_schedule(obj)
        rows=list(current_roster(obj))
        if not rows:raise Conflict('The dated roster is empty.')
        if len(rows)>500:raise Conflict('Register limit is 500 students.')
        for row in rows:
            save(m.StudentAttendance(class_session=obj,course_offering_section_student=row,course_offering_section=obj.course_offering_section,student_id=row.course_registration.term_registration.enrolment.student_id))
        obj.register_status='OPEN'
    elif action=='finalize':
        if obj.register_status not in ['OPEN','REOPENED']:raise Conflict('Register is not open.')
        edit_window(obj);end_has_passed(obj);assert_schedule(obj);assert_roster(obj)
        rows=m.StudentAttendance.objects.select_for_update().filter(class_session=obj).select_related('attendance_status')
        if not rows.exists() or rows.filter(is_eligible=True,attendance_status__isnull=True).exists():raise Conflict('Resolve every unmarked student explicitly before finalization.')
        for row in rows:
            previous=snapshot(row);apply_contribution(obj,row);row.version+=1;save(row);audit(row,actor,obj.course_offering_section,'attendance_finalized',reason,previous)
        obj.register_status='FINALIZED';obj.finalized_at=timezone.now()
    elif action=='reopen':
        if obj.register_status not in ['FINALIZED','OPEN']:raise Conflict('Only a finalized or late open register can be reopened.')
        if m.CorrectionRequest.objects.filter(attendance__class_session=obj,request_status='PENDING').exists():raise Conflict('Resolve pending corrections before reopening.')
        obj.register_status='REOPENED'
    else:raise ValidationError('Unknown session action.')
    return update_session(obj,actor,reason,'register_'+action,before)

def apply_contribution(session,row):
    if not row.is_eligible:
        row.credit=row.denominator=Decimal(0);return
    rule=session.policy.rules.get(row.attendance_status.status_code)
    if rule is None:raise Conflict('Status is not allowed by the frozen policy.')
    duration=(datetime.combine(session.session_date,session.end_time)-datetime.combine(session.session_date,session.start_time)).total_seconds()/60
    row.credit,row.denominator=contribution(rule=rule,basis=session.policy.basis,duration_minutes=duration)

@command
def mark(*,actor,session_id,expected_version,entries,reason):
    globals()['reason'](reason);obj=session_for(actor,session_id,'mark_attendance');version(obj,expected_version)
    if obj.register_status not in ['OPEN','REOPENED']:raise Conflict('Open register required.')
    edit_window(obj);end_has_passed(obj);assert_schedule(obj);assert_roster(obj)
    if not 1<=len(entries)<=500:raise ValidationError('Mark between 1 and 500 entries.')
    if len({str(row['attendance_id']) for row in entries})!=len(entries):raise ValidationError('Duplicate attendance row.')
    existing={row.pk:row for row in m.StudentAttendance.objects.select_for_update().filter(class_session=obj)}
    statuses={row.pk:row for row in m.AttendanceStatus.objects.filter(is_active=True)}
    for entry in entries:
        row=existing.get(int(entry['attendance_id']))
        if row is None or not row.is_eligible:raise NotFound('Attendance row unavailable.')
        status=statuses.get(int(entry['status_id'])) if entry.get('status_id') else None
        if status is None or status.status_code not in obj.policy.rules:raise ValidationError('Select an explicit status allowed by the frozen policy.')
        old=snapshot(row);row.attendance_status=status;row.remarks=entry.get('remarks','');row.marked_by_user=actor;row.marked_at=timezone.now();row.version+=1
        row.credit=row.denominator=None;save(row);audit(row,actor,obj.course_offering_section,'attendance_marked',reason,old)
    return update_session(obj,actor,reason,'register_saved',snapshot(obj))

@command
def request_correction(*,actor,attendance_id,expected_version,status_id,reason,evidence_reference=''):
    globals()['reason'](reason)
    row=m.StudentAttendance.objects.select_for_update().select_related('class_session__policy','attendance_status').get(pk=attendance_id)
    try:require_session(actor,row.class_session,'mark_attendance')
    except NotFound:
        if own_student(actor)!=row.student_id:raise NotFound()
    version(row,expected_version)
    obj=row.class_session
    if obj.register_status!='FINALIZED' or row.attendance_status_id is None or not row.is_eligible:raise Conflict('Corrections require a finalized marked register.')
    if (timezone.localdate()-obj.session_date).days>obj.policy.correction_days:raise Conflict('Correction request window has closed.')
    status=m.AttendanceStatus.objects.get(pk=status_id,is_active=True)
    if status.status_code not in obj.policy.rules or status.pk==row.attendance_status_id:raise ValidationError('Requested status must differ and belong to the frozen policy.')
    correction=save(m.CorrectionRequest(attendance=row,old_status=row.attendance_status,requested_status=status,attendance_version=row.version,requested_by=actor,reason=reason,evidence_reference=evidence_reference))
    audit(correction,actor,obj.course_offering_section,'correction_requested',reason);return correction

@command
def decide_correction(*,actor,correction_id,expected_version,decision,reason):
    globals()['reason'](reason)
    obj=m.CorrectionRequest.objects.select_for_update().select_related('attendance__class_session__policy','requested_status').get(pk=correction_id)
    row=m.StudentAttendance.objects.select_for_update().get(pk=obj.attendance_id);session=row.class_session
    if decision=='CANCELLED':
        if obj.requested_by_id!=actor.pk:raise PermissionDenied('Only the requester may cancel.')
        try:require_session(actor,session,'mark_attendance')
        except NotFound:
            if own_student(actor)!=row.student_id:raise NotFound()
    else:
        require_session(actor,session,'review_attendance')
        if obj.requested_by_id==actor.pk:raise PermissionDenied('A different authorized reviewer must decide.')
    version(obj,expected_version)
    if obj.request_status!='PENDING' or decision not in ['APPROVED','REJECTED','CANCELLED']:raise Conflict('Correction is no longer pending.')
    before=snapshot(obj)
    if decision=='APPROVED':
        if session.register_status!='FINALIZED' or row.version!=obj.attendance_version or row.attendance_status_id!=obj.old_status_id:raise Conflict('Attendance changed since this request.')
        previous=snapshot(row);row.attendance_status=obj.requested_status;row.version+=1;row.marked_by_user=actor;row.marked_at=timezone.now()
        apply_contribution(session,row);save(row);audit(row,actor,session.course_offering_section,'attendance_corrected',reason,previous)
        update_session(session,actor,reason,'register_corrected',snapshot(session))
    obj.request_status=decision;obj.resolved_by=actor;obj.resolved_at=timezone.now();obj.resolution_remarks=reason;obj.version+=1;save(obj)
    audit(obj,actor,session.course_offering_section,'correction_decided',reason,before);return obj

@command
def revise_lessons(*,actor,section_id,expected_number,topics,reason):
    globals()['reason'](reason);section=require_section(actor,section_id,'manage_attendance')
    latest=m.LessonRevision.objects.filter(section=section).order_by('-number').first()
    if (latest.number if latest else 0)!=expected_number:raise Conflict('Stale lesson revision.')
    if not 1<=len(topics)<=200 or len({row['key'] for row in topics})!=len(topics):raise ValidationError('Use 1–200 uniquely keyed ordered topics.')
    term=section.programme_term_offering.academic_term
    for row in topics:
        if not term.start_date<=row['planned_date']<=term.end_date:raise ValidationError('Topic planned date must fit the term.')
    canonical=json.loads(json.dumps(topics,cls=DjangoJSONEncoder))
    if latest:
        covered=set(m.TopicCoverage.objects.filter(lesson_revision__section=section).values_list('topic_key',flat=True))
        old={row['key']:row for row in latest.topics};new={row['key']:row for row in canonical}
        if any(key not in new or new[key]['title']!=old[key]['title'] for key in covered):raise Conflict('Covered topic identity cannot be removed or renamed; add a successor topic.')
    obj=save(m.LessonRevision(section=section,number=expected_number+1,topics=canonical,actor=actor,reason=reason))
    audit(obj,actor,section,'lessons_revised',reason);return obj

@command
def record_coverage(*,actor,session_id,expected_version,lesson_revision_id,topic_key,percent,minutes,reason):
    globals()['reason'](reason);session=session_for(actor,session_id,'manage_attendance');version(session,expected_version)
    if session.session_status!='CONDUCTED':raise Conflict('Coverage requires a conducted session.')
    revision=m.LessonRevision.objects.get(pk=lesson_revision_id,section=session.course_offering_section)
    if topic_key not in {t['key'] for t in revision.topics}:raise ValidationError('Unknown topic.')
    existing=m.TopicCoverage.objects.filter(lesson_revision__section=revision.section,topic_key=topic_key).aggregate(total=models.Sum('percent'))['total'] or 0
    if existing+percent>100:raise Conflict('Topic coverage exceeds 100 percent.')
    elapsed=m.TopicCoverage.objects.filter(session=session).aggregate(total=models.Sum('minutes'))['total'] or 0
    duration=(datetime.combine(session.session_date,session.end_time)-datetime.combine(session.session_date,session.start_time)).total_seconds()/60
    if elapsed+minutes>duration:raise Conflict('Coverage exceeds session contact time.')
    obj=save(m.TopicCoverage(session=session,lesson_revision=revision,topic_key=topic_key,percent=percent,minutes=minutes,remarks=reason,actor=actor))
    audit(obj,actor,session.course_offering_section,'coverage_recorded',reason)
    update_session(session,actor,reason,'lesson_executed',snapshot(session));return obj


@command
def reconcile_register(*,actor,session_id,expected_version,reason):
    globals()['reason'](reason);obj=session_for(actor,session_id,'review_attendance');version(obj,expected_version)
    if obj.register_status not in ['OPEN','REOPENED']:raise Conflict('Explicitly reopen finalized registers before reconciling their roster.')
    current={row.pk:row for row in current_roster(obj)}
    existing={row.course_offering_section_student_id:row for row in m.StudentAttendance.objects.select_for_update().filter(class_session=obj)}
    if len(current)>500:raise Conflict('Register limit is 500 students.')
    for pk,row in existing.items():
        eligible=pk in current
        if row.is_eligible!=eligible:
            previous=snapshot(row);row.is_eligible=eligible;row.exclusion_reason='' if eligible else reason;row.version+=1
            row.credit=row.denominator=None;save(row);audit(row,actor,obj.course_offering_section,'roster_reconciled',reason,previous)
    for pk,episode in current.items():
        if pk not in existing:
            row=save(m.StudentAttendance(class_session=obj,course_offering_section_student=episode,course_offering_section=obj.course_offering_section,student_id=episode.course_registration.term_registration.enrolment.student_id))
            audit(row,actor,obj.course_offering_section,'roster_added',reason)
    return update_session(obj,actor,reason,'roster_reconciled',snapshot(obj))
