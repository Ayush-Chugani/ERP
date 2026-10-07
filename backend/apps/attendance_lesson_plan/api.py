import csv,io
from datetime import date
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError,NotFound,PermissionDenied
from rest_framework.throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema,OpenApiTypes
from apps.core.pagination import BoundedPagination
from . import models as m,selectors as q,commands as c,services as s
from .policies import sections,require_section,require_session,enabled,own_student

class AttendanceThrottle(UserRateThrottle):
    scope='attendance'
    rate='120/min'
class AttendanceView(APIView):
    throttle_classes=[AttendanceThrottle]
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response['Cache-Control']='private, no-store';patch_vary_headers(response,['Authorization','Cookie']);return response
def command_view(operation):
    class Command(AttendanceView):
        @extend_schema(request=c.COMMANDS[operation][0],responses=c.Result,operation_id='attendance_'+operation.replace('-','_'))
        def post(self,request):
            return Response(c.execute(actor=request.user,operation=operation,data=request.data,key=request.headers.get('Idempotency-Key','')))
    return Command.as_view()

class Records(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource):
        actor=request.user
        if not enabled(actor,'view_attendance'):raise PermissionDenied('Attendance read authority is required.')
        if resource=='sessions':qs=q.sessions(actor)
        elif resource=='policies':qs=m.PolicyRevision.objects.filter(section__in=sections(actor))
        elif resource=='lessons':qs=m.LessonRevision.objects.filter(section__in=sections(actor))
        elif resource=='coverage':qs=m.TopicCoverage.objects.filter(session__in=q.sessions(actor))
        elif resource=='corrections':qs=m.CorrectionRequest.objects.filter(attendance__class_session__in=q.sessions(actor))
        elif resource=='statuses':qs=m.AttendanceStatus.objects.all()
        elif resource=='audit':
            if not enabled(actor,'review_attendance'):raise PermissionDenied()
            from django.db.models import Q
            scope=q.sessions(actor,'review_attendance')
            qs=m.AuditEvent.objects.filter(section__in=sections(actor,'review_attendance')).filter(
                Q(resource__in=['policyrevision','lessonrevision'])|
                Q(resource='classsession',record_id__in=scope.values('pk'))|
                Q(resource='studentattendance',record_id__in=m.StudentAttendance.objects.filter(class_session__in=scope).values('pk'))|
                Q(resource='correctionrequest',record_id__in=m.CorrectionRequest.objects.filter(attendance__class_session__in=scope).values('pk'))|
                Q(resource='topiccoverage',record_id__in=m.TopicCoverage.objects.filter(session__in=scope).values('pk')))
        else:raise NotFound()
        if request.query_params.get('section_id') and resource not in ('statuses',):
            try:pk=int(request.query_params['section_id'])
            except ValueError:raise ValidationError('Invalid section ID.')
            path={'sessions':'course_offering_section_id','coverage':'session__course_offering_section_id','corrections':'attendance__course_offering_section_id'}.get(resource,'section_id')
            qs=qs.filter(**{path:pk})
        pager=BoundedPagination();page=pager.paginate_queryset(qs.order_by('pk'),request)
        return pager.get_paginated_response([q.record(obj) for obj in page])

class Register(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        try:return Response(q.register(request.user,pk))
        except m.ClassSession.DoesNotExist:raise NotFound()

class Lookups(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource):
        actor=request.user
        if not enabled(actor,'view_attendance'):raise PermissionDenied()
        if resource=='sections':
            qs=sections(actor).select_related('course_offering__course','class_section')
            label=lambda r:f'{r.course_offering.course.course_code} / {r.class_section.section_code} / {r.session_type}'
        elif resource=='occurrences':
            from apps.teaching_timetable.models import PublishedOccurrence
            qs=PublishedOccurrence.objects.filter(revision__status='PUBLISHED',course_offering_section__in=sections(actor)).select_related('course_offering_section__course_offering__course')
            label=lambda r:f'{r.course_offering_section.course_offering.course.course_code} / {r.date} / {r.start_time}'
        elif resource in ('faculty','rooms'):
            try:section=require_section(actor,int(request.query_params.get('section_id','0')),'view_attendance')
            except ValueError:raise ValidationError('Invalid section ID.')
            if resource=='faculty':
                from apps.teaching_timetable.models import FacultyAssignment
                qs=FacultyAssignment.objects.filter(course_offering_section=section,assignment_status__in=['ACTIVE','COMPLETED']).select_related('employee')
                qs=qs.filter(pk__in=[r.pk for r in qs if sections(actor,employee_id=r.employee_id).filter(pk=section.pk).exists()])
                label=lambda r:r.employee.display_name
            else:
                from apps.organization.models import Room
                qs=Room.objects.filter(building__campus=section.programme_term_offering.programme.department.campus,is_active=True)
                qs=qs.filter(pk__in=[r.pk for r in qs if sections(actor,room_id=r.pk).filter(pk=section.pk).exists()])
                label=lambda r:r.room_code
        else:raise NotFound()
        if request.query_params.get('section_id') and resource in ('sections','occurrences'):
            try:pk=int(request.query_params['section_id'])
            except ValueError:raise ValidationError('Invalid section ID.')
            qs=qs.filter(**{('pk' if resource=='sections' else 'course_offering_section_id'):pk})
        pager=BoundedPagination();page=pager.paginate_queryset(qs.order_by('pk'),request)
        return pager.get_paginated_response([{'id':str(row.pk),'label':label(row)} for row in page])

class Mine(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        rows=q.attendance_rows(request.user,True).order_by('-class_session__session_date','pk')
        pager=BoundedPagination();page=pager.paginate_queryset(rows,request)
        return pager.get_paginated_response([{'id':str(row.pk),'version':row.version,'session_id':str(row.class_session_id),'date':row.class_session.session_date,'status':row.attendance_status.status_code if row.attendance_status_id else None,'is_eligible':row.is_eligible,'allowed_statuses':[{'id':str(status.pk),'status_name':status.status_name} for status in m.AttendanceStatus.objects.filter(status_code__in=row.class_session.policy.rules)],'credit':row.credit,'denominator':row.denominator,'policy_id':str(row.class_session.policy_id)} for row in page])

def dates(request):
    try:start=date.fromisoformat(request.query_params['date_from']);end=date.fromisoformat(request.query_params['date_to'])
    except (ValueError,KeyError):raise ValidationError('Supply date_from and date_to in YYYY-MM-DD form.')
    return start,end

class Report(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        start,end=dates(request)
        personal=request.query_params.get('mine')=='true'
        if not personal and not enabled(request.user,'view_attendance'):raise PermissionDenied()
        return Response({'results':q.report(request.user,start,end,personal)})

class Export(AttendanceView):
    @extend_schema(responses={(200,'text/csv'):OpenApiTypes.STR})
    def get(self,request):
        if not enabled(request.user,'export_attendance'):raise PermissionDenied()
        start,end=dates(request);rows=q.report(request.user,start,end)
        stream=io.StringIO();writer=csv.writer(stream)
        if rows:
            writer.writerow(rows[0])
            for row in rows:writer.writerow([("'"+str(value)) if str(value).lstrip().startswith(('=','+','-','@')) else value for value in row.values()])
        response=HttpResponse(stream.getvalue(),content_type='text/csv');response['Content-Disposition']='attachment; filename="attendance.csv"';return response

class Reconcile(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        if not enabled(request.user,'view_attendance'):raise PermissionDenied()
        return Response({'results':q.reconcile(request.user)})

class LessonProgress(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        section=require_section(request.user,pk,'view_attendance')
        revision=m.LessonRevision.objects.filter(section=section).order_by('-number').first()
        from django.db.models import Sum
        totals={r['topic_key']:r for r in m.TopicCoverage.objects.filter(lesson_revision__section=section,session__in=q.sessions(request.user)).values('topic_key').annotate(percent=Sum('percent'),minutes=Sum('minutes'))}
        today=date.today().isoformat()
        return Response({'revision':q.record(revision) if revision else None,'topics':[{**topic,'covered_percent':totals.get(topic['key'],{}).get('percent',0),'covered_minutes':totals.get(topic['key'],{}).get('minutes',0),'overdue':topic['planned_date']<today and totals.get(topic['key'],{}).get('percent',0)<100} for topic in revision.topics] if revision else []})

class History(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        row=m.StudentAttendance.objects.filter(pk=pk).select_related('class_session').first()
        if row is None:raise NotFound()
        try:require_session(request.user,row.class_session,'view_attendance')
        except NotFound:
            if own_student(request.user)!=row.student_id:raise NotFound()
        events=m.AuditEvent.objects.filter(resource='studentattendance',record_id=row.pk).order_by('pk')
        pager=BoundedPagination();page=pager.paginate_queryset(events,request)
        return pager.get_paginated_response([{'id':str(event.pk),'action':event.action,'created_at':event.created_at,'before':event.before,'after':event.after} for event in page])


class MyCorrections(AttendanceView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        qs=m.CorrectionRequest.objects.filter(attendance__student_id=own_student(request.user),requested_by=request.user).order_by('-pk')
        pager=BoundedPagination();page=pager.paginate_queryset(qs,request)
        return pager.get_paginated_response([q.record(row) for row in page])
