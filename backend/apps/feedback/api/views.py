import json,csv,io
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import NotFound,ValidationError,PermissionDenied
from rest_framework.throttling import UserRateThrottle,AnonRateThrottle
from drf_spectacular.utils import extend_schema,OpenApiTypes
from apps.core.pagination import BoundedPagination
from apps.academic_calendar.models import AcademicTerm
from apps.organization.models import Programme
from .. import models as m,services as s,permissions as p,selectors as q
from . import commands as c
from .serializers import COMMANDS,Result,Submission,Target
class UserRate(UserRateThrottle):scope='feedback';rate='60/min'
class PublicRate(AnonRateThrottle):scope='feedback_public';rate='20/min'
class Base(APIView):
    def initial(self,request,*a,**kw):
        super().initial(request,*a,**kw)
        from django.conf import settings
        if not settings.FEEDBACK_ENABLED:raise PermissionDenied('Feedback is disabled.')
    throttle_classes=[UserRate,PublicRate]
    def finalize_response(self,request,response,*a,**kw):
        response=super().finalize_response(request,response,*a,**kw);response['Cache-Control']='private, no-store';patch_vary_headers(response,['Authorization','Cookie']);return response
def command_view(operation):
    class Command(Base):
        @extend_schema(request=COMMANDS[operation][0],responses=Result,operation_id='feedback_'+operation.replace('-','_'))
        def post(self,request):return Response(c.execute(actor=request.user,operation=operation,data=request.data,key=request.headers.get('Idempotency-Key','')))
    return Command.as_view()
class Records(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource):
        actor=request.user;bank=p.institutions(actor,'manage_question_bank');forms=p.institutions(actor,'manage_questionnaires');cycle_inst=p.institutions(actor,'manage_cycles');programmes=p.scheduling_programmes(actor)
        from apps.organization.models import Institution
        schedule_inst=Institution.objects.filter(pk__in=programmes.values('department__campus__institution_id'))|cycle_inst
        if resource=='categories':qs=m.Category.objects.filter(institution__in=bank)
        elif resource=='questions':qs=m.Question.objects.filter(feedback_category__institution__in=bank)
        elif resource=='choices':qs=m.Choice.objects.filter(feedback_question__feedback_category__institution__in=bank)
        elif resource=='questionnaires':qs=(m.Questionnaire.objects.filter(institution__in=forms)|m.Questionnaire.objects.filter(institution__in=schedule_inst,status='ACTIVE')).distinct()
        elif resource=='items':qs=m.QuestionnaireItem.objects.filter(questionnaire__institution__in=forms)
        elif resource=='cycles':qs=(p.cycles(actor)|p.cycles(actor,'view_admin_results')|q.faculty_cycles(actor)).distinct()
        elif resource=='institutions':qs=(bank|forms|schedule_inst).distinct()
        elif resource=='programmes':qs=programmes
        elif resource=='terms':
            if not schedule_inst.exists():raise PermissionDenied()
            qs=AcademicTerm.objects.all()
        elif resource=='audit':qs=m.Audit.objects.filter(institution__in=p.institutions(actor,'view_admin_results'))
        else:raise NotFound()
        if request.query_params.get('search') and resource in ['categories','questions','questionnaires','cycles']:
            field={'categories':'category_name','questions':'question_text','questionnaires':'questionnaire_name','cycles':'cycle_name'}[resource];qs=qs.filter(**{field+'__icontains':request.query_params['search'][:150]})
        for field in ['status','response_type','is_active','academic_term_id','questionnaire_id','feedback_category_id','feedback_question_id']:
            value=request.query_params.get(field)
            if value is not None and any(f.attname==field for f in qs.model._meta.fields):
                if field.endswith('_id'):
                    try:value=int(value)
                    except ValueError:raise ValidationError('Invalid ID filter.')
                if field=='is_active':value=value=='true'
                qs=qs.filter(**{field:value})
        pager=BoundedPagination();rows=pager.paginate_queryset(qs.order_by('pk'),request)
        return pager.get_paginated_response([{**{k:v for k,v in s.snapshot(row).items() if k not in ['frozen','key_fingerprint','explicit_registrations']},'id':str(row.pk)} for row in rows])
class Available(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):return Response({'results':q.available(request.user)})
def target(request):
    values={key:request.query_params[key] for key in ['course_offering_id','faculty_assignment_id'] if key in request.query_params};parsed=Target(data=values);parsed.is_valid(raise_exception=True);return parsed.validated_data
class Questionnaire(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        try:return Response(q.questionnaire(request.user,pk,target(request)))
        except m.Cycle.DoesNotExist:raise NotFound()
@method_decorator(sensitive_post_parameters(),name='dispatch')
class Submit(Base):
    @extend_schema(request=Submission,responses=OpenApiTypes.OBJECT)
    def post(self,request,pk):
        parsed=Submission(data=request.data);parsed.is_valid(raise_exception=True)
        return Response(s.submit(actor=request.user,cycle_id=pk,**parsed.validated_data,key=request.headers.get('Idempotency-Key','')))
class Readiness(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        obj=m.Questionnaire.objects.filter(pk=pk,institution__in=p.institutions(request.user,'manage_questionnaires')).first()
        if not obj:raise NotFound()
        return Response({'ready':True,'questionnaire':s.readiness(obj)})
class Results(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):return Response(q.aggregates(request.user,pk,request.query_params.get('target','')))
class PublicResults(Base):
    permission_classes=[AllowAny];authentication_classes=[]
    @extend_schema(responses=OpenApiTypes.OBJECT,auth=[])
    def get(self,request,pk):return Response(q.aggregates(request.user,pk,request.query_params.get('target',''),True))
class Export(Base):
    @extend_schema(responses={(200,'text/csv'):OpenApiTypes.STR})
    def get(self,request,pk):
        obj=p.cycle(request.user,pk,'export_results');data=q.aggregates(request.user,pk,request.query_params.get('target',''))
        stream=io.StringIO();writer=csv.writer(stream)
        writer.writerow(['cycle','target','generated_at','minimum_cohort','suppressed','response_count'])
        writer.writerow([data['cycle_id'],data['target'],data['generated_at'],data['minimum_cohort'],data['suppressed'],data['response_count']])
        writer.writerow(['scoring',data['scoring']]);writer.writerow(['item','question','metrics'])
        for row in data['questions']:
            values=[row['item_id'],row['text'],json.dumps({k:v for k,v in row.items() if k not in ['item_id','text']})]
            writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=','+','-','@')) else v for v in values])
        s.audit(obj,request.user,obj.questionnaire.institution_id,'aggregate_export','Aggregate CSV exported')
        response=HttpResponse(stream.getvalue(),content_type='text/csv');response['Content-Disposition']='attachment; filename="feedback.csv"';return response
class TextReview(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        obj=p.cycle(request.user,pk,'view_text_feedback');key=request.query_params.get('target','')
        if not obj.allow_text_review:raise NotFound()
        data=q.aggregates(request.user,pk,key)
        if data['suppressed']:return Response({'suppressed':True,'results':[]})
        allowed=[row['item_id'] for row in data['questions'] if row['response_type']=='TEXT' and not row['suppressed']]
        rows=m.ResponseItem.objects.filter(feedback_response__feedback_cycle=obj,feedback_response__target_key=key,questionnaire_item_id__in=allowed,text_response__isnull=False).order_by('pk')
        pager=BoundedPagination();page=pager.paginate_queryset(rows,request)
        s.audit(obj,request.user,obj.questionnaire.institution_id,'text_review','Deidentified text review')
        return pager.get_paginated_response([{'questionnaire_item_id':str(row.questionnaire_item_id),'text':row.text_response} for row in page])


class ResultTargets(Base):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,pk):
        obj=m.Cycle.objects.filter(pk=pk,status='CLOSED').first()
        if not obj:raise NotFound()
        if p.cycles(request.user,'view_admin_results').filter(pk=pk).exists():
            keys=m.Response.objects.filter(feedback_cycle=obj).values_list('target_key',flat=True).distinct().order_by('target_key')
            if keys.count()>500:raise ValidationError('Too many targets for this dashboard.')
            return Response({'results':[{'id':key,'label':key} for key in keys]})
        if not q.faculty_cycles(request.user).filter(pk=pk).exists():raise NotFound()
        from apps.teaching_timetable.models import FacultyAssignment
        from apps.people_master.models import AccountLink
        assignments=FacultyAssignment.objects.filter(employee_id__in=AccountLink.objects.filter(user=request.user,employee__employment_status='ACTIVE').values('employee_id'),course_offering_section__programme_term_offering__academic_term_id=obj.academic_term_id)
        keys=[]
        for assignment in assignments:
            key='faculty:'+str(assignment.pk)
            try:q.result_scope(request.user,pk,key);keys.append({'id':key,'label':key})
            except NotFound:continue
        return Response({'results':keys})
