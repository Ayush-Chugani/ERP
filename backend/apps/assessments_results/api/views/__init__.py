import csv,io
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,NotFound,ValidationError
from rest_framework.throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema,OpenApiTypes
from apps.core.pagination import BoundedPagination
from apps.term_registration import models as reg
from ... import models as m,permissions as p,selectors as q,services as s
from .. import commands as c
from ..serializers import COMMANDS,Result
class Rate(UserRateThrottle):scope='assessments';rate='120/min'
class Base(APIView):
    throttle_classes=[Rate]
    def finalize_response(self,request,response,*a,**kw):
        response=super().finalize_response(request,response,*a,**kw);response['Cache-Control']='private, no-store';patch_vary_headers(response,['Authorization','Cookie']);return response
def command_view(operation):
    class Command(Base):
        @extend_schema(request=COMMANDS[operation][0],responses=Result,operation_id='assessment_'+operation.replace('-','_'))
        def post(self,request):return Response(c.execute(actor=request.user,operation=operation,data=request.data,key=request.headers.get('Idempotency-Key','')))
    return Command.as_view()
def records(actor,resource):
    if not p.enabled(actor,'view'):raise PermissionDenied()
    off=p.offerings(actor)
    if resource=='offerings':return off
    if resource=='components':return m.AssessmentComponent.objects.filter(course_offering__in=off)
    if resource=='policies':return m.CalculationPolicy.objects.filter(course_offering__in=off)
    if resource=='events':return q.events(actor)
    if resource=='course-results':return q.course_results(actor)
    if resource=='term-results':return q.term_results(actor)
    if resource=='registrations':return q.scoped_registrations(actor)
    if resource=='terms':
        if not p.enabled(actor,'calculate'):raise PermissionDenied()
        return reg.StudentTermRegistration.objects.filter(programme_term_offering_id__in=p.offerings(actor,'calculate').values('programme_term_offering_id'))
    if resource=='scales':return m.GradeScale.objects.filter(institution_id__in=off.values('programme_term_offering__programme__department__campus__institution_id'))
    if resource=='grades':return m.GradeRule.objects.filter(grade_scale__in=records(actor,'scales'))
    if resource=='audit':
        if not p.enabled(actor,'publish'):raise PermissionDenied()
        return m.Audit.objects.filter(course_offering__in=p.offerings(actor,'publish'))
    raise NotFound()
class Records(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource):
        qs=records(request.user,resource)
        if request.query_params.get('offering_id'):
            try:pk=int(request.query_params['offering_id'])
            except ValueError:raise ValidationError('Invalid offering ID.')
            path='course_registration__course_offering_id' if resource=='course-results' else 'pk' if resource=='offerings' else 'course_offering_id'
            if resource not in ['terms','term-results','scales','grades']:qs=qs.filter(**{path:pk})
        page=BoundedPagination();rows=page.paginate_queryset(qs.order_by('pk'),request)
        return page.get_paginated_response([{**{k:value for k,value in s.snapshot(row).items() if k!='roster'},'id':str(row.pk)} for row in rows])
class Roster(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        try:return Response(q.roster(request.user,pk))
        except m.AssessmentEvent.DoesNotExist:raise NotFound()
class Mine(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):return Response({'results':q.student_results(request.user)})
class Export(Base):
    @extend_schema(responses={(200,'text/csv'):OpenApiTypes.STR})
    def get(self,request,resource):
        if not p.enabled(request.user,'export'):raise PermissionDenied()
        if resource not in ['course-results','term-results']:raise NotFound()
        rows=q.course_results(request.user,'export') if resource=='course-results' else q.term_results(request.user,'export')
        if rows.count()>10000:raise ValidationError('Export limit is 10,000 records; narrow institutional scope.')
        stream=io.StringIO();writer=csv.writer(stream);fields=['id','result_status','credits_earned','total_marks','grade_letter','grade_point'] if resource=='course-results' else ['id','result_status','credits_registered','credits_earned','sgpa','cgpa']
        writer.writerow(fields)
        for row in rows:
            vals=[str(row.pk) if field=='id' else str(getattr(row,field,'')) for field in fields];writer.writerow(["'"+val if val.lstrip().startswith(('=','+','-','@')) else val for val in vals])
        response=HttpResponse(stream.getvalue(),content_type='text/csv');response['Content-Disposition']='attachment; filename="results.csv"';return response


class Report(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource):
        if resource in ['mark-sheet','exceptions']:
            try:pk=int(request.query_params.get('event_id','0'))
            except ValueError:raise ValidationError('Invalid event ID.')
            try:data=q.roster(request.user,pk)
            except m.AssessmentEvent.DoesNotExist:raise NotFound()
            rows=data['rows']
            if resource=='exceptions':rows=[r for r in rows if not r['mark'] or r['mark']['attendance_status']!='PRESENT']
        elif resource=='grade-distribution':
            if not p.enabled(request.user,'view'):raise PermissionDenied()
            from django.db.models import Count
            rows=list(q.course_results(request.user).filter(state='PUBLISHED',is_withheld=False).values('course_registration__course_offering_id','grade_letter','result_status').annotate(count=Count('pk')))
        else:raise NotFound()
        return Response({'results':rows})


class Batch(Base):
    @extend_schema(request=OpenApiTypes.OBJECT,responses=OpenApiTypes.OBJECT)
    def post(self,request):
        if not isinstance(request.data,dict) or set(request.data)!={'rows'}:raise ValidationError('Expected rows only.')
        return Response({'results':c.execute_batch(actor=request.user,rows=request.data['rows'],key=request.headers.get('Idempotency-Key',''))})
