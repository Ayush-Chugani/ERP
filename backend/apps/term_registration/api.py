import csv
import io
from datetime import date
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.throttling import UserRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiTypes
from apps.core.pagination import BoundedPagination
from . import commands as c, execution as e, selectors as s
from .policies import permitted, programmes
from .workflows import RESOURCES


class RegistrationThrottle(UserRateThrottle):
    scope = 'registration'
    rate = '120/min'


class RegistrationView(APIView):
    throttle_classes = [RegistrationThrottle]
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response['Cache-Control']='private, no-store'
        patch_vary_headers(response,['Authorization','Cookie'])
        return response


def read_action(actor):
    if permitted(actor,'view_registration'): return 'view_registration'
    if permitted(actor,'manage_registration'): return 'manage_registration'
    raise PermissionDenied('Registration read permission required.')


class Records(RegistrationView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource,pk=None):
        if resource not in RESOURCES: raise NotFound()
        qs=s.scoped(request.user,resource,read_action(request.user))
        if pk:
            obj=qs.filter(pk=pk).first()
            if obj is None: raise NotFound()
            return Response(s.record(obj))
        if request.query_params.get('offering_id'):
            field={'offerings':'pk','batches':'class_section__programme_term_offering_id','rosters':'course_offering__programme_term_offering_id'}.get(resource,'programme_term_offering_id')
            if resource not in ('policies','audit'):
                try: value=int(request.query_params['offering_id'])
                except ValueError: raise ValidationError('Invalid offering ID.')
                qs=qs.filter(**{field:value})
        if request.query_params.get('programme_id'):
            try: value=int(request.query_params['programme_id'])
            except ValueError: raise ValidationError('Invalid programme ID.')
            qs=qs.filter(**{RESOURCES[resource][1]+'_id':value})
        if resource=='rosters' and request.query_params.get('as_of'):
            try: day=date.fromisoformat(request.query_params['as_of'])
            except ValueError: raise ValidationError('Invalid as-of date.')
            qs=s.as_of_roster(qs,day)
        pager=BoundedPagination()
        rows=pager.paginate_queryset(qs.order_by('pk'),request)
        return pager.get_paginated_response(s.records_with_capacity(resource,rows))


def command_view(operation):
    serializer,_=c.COMMANDS[operation]
    class Command(RegistrationView):
        @extend_schema(request=serializer,responses=c.Result,operation_id='registration_'+operation.replace('-','_'))
        def post(self,request):
            return Response(e.execute(actor=request.user,operation=operation,data=request.data,key=request.headers.get('Idempotency-Key','')))
    return Command.as_view()


class BulkThrottle(RegistrationThrottle):
    scope='registration_bulk'
    rate='20/min'


class Bulk(RegistrationView):
    throttle_classes=[BulkThrottle]
    @extend_schema(request=c.Bulk,responses=OpenApiTypes.OBJECT)
    def post(self,request):
        payload=c.Bulk(data=request.data);payload.is_valid(raise_exception=True)
        return Response({'results':e.bulk(actor=request.user,key=request.headers.get('Idempotency-Key',''),**payload.validated_data),'dry_run':payload.validated_data['dry_run']})


class Personal(RegistrationView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        from .models import StudentCourseRegistration
        terms=s.personal(request.user)
        pager=BoundedPagination(); page=pager.paginate_queryset(terms.order_by('pk'),request)
        return pager.get_paginated_response([{'id':str(term.pk),'offering_id':str(term.programme_term_offering_id),'status':term.registration_status,'roll_number':term.roll_number,
            'courses':[{'id':str(row.pk),'course':row.course_offering.course.course_code,'status':row.registration_status} for row in StudentCourseRegistration.objects.filter(term_registration=term).select_related('course_offering__course')]} for term in page])


class Export(RegistrationView):
    @extend_schema(responses={(200,'text/csv'):OpenApiTypes.STR})
    def get(self,request,resource):
        if resource not in RESOURCES or resource in ('audit','policies'): raise NotFound()
        if not permitted(request.user,'export_registration'): raise PermissionDenied()
        qs=s.scoped(request.user,resource,'export_registration').order_by('pk')
        if request.query_params.get('offering_id') and resource not in ('offerings',):
            field={'batches':'class_section__programme_term_offering_id','rosters':'course_offering__programme_term_offering_id'}.get(resource,'programme_term_offering_id')
            try: qs=qs.filter(**{field:int(request.query_params['offering_id'])})
            except ValueError: raise ValidationError('Invalid offering ID.')
        if qs.count()>10000: raise ValidationError('Narrow the export to at most 10,000 rows.')
        data=[s.record(row) for row in qs]
        stream=io.StringIO(); writer=csv.writer(stream)
        if data:
            writer.writerow(data[0].keys())
            for row in data:
                writer.writerow([("'" + str(value)) if str(value).lstrip().startswith(('=','+','-','@')) else value for value in row.values()])
        response=HttpResponse(stream.getvalue(),content_type='text/csv')
        response['Content-Disposition']=f'attachment; filename="registration-{resource}.csv"'
        return response


class Lookups(RegistrationView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request,resource):
        from apps.academic_calendar.models import AcademicTerm, Semester
        from apps.curriculum_catalog.models import CurriculumScheme, CurriculumCourse, CourseCatalog
        from apps.admission_enrolment.models import StudentProgrammeEnrolment
        from apps.organization.models import Room, ProgrammeSpecialization
        actor=request.user; action=read_action(actor)
        if resource=='programmes':
            qs=programmes(actor,action); label=lambda row:row.programme_name
        else:
            try: programme=programmes(actor,action).get(pk=int(request.query_params.get('programme_id','0')))
            except (ValueError,programmes(actor,action).model.DoesNotExist): raise NotFound()
            resources={
                'terms':(AcademicTerm.objects.exclude(status__in=['CLOSED','CANCELLED']),lambda r:r.term_name,None),
                'semesters':(Semester.objects.all(),lambda r:r.semester_name,None),
                'schemes':(CurriculumScheme.objects.filter(programme=programme,status='ACTIVE'),lambda r:r.scheme_name,'schemes'),
                'specializations':(ProgrammeSpecialization.objects.filter(programme=programme,is_active=True),lambda r:str(r),'specializations'),
                'curriculum-courses':(CurriculumCourse.objects.filter(curriculum_scheme__programme=programme).select_related('course'),lambda r:r.course.course_code,'curriculum-courses'),
                'catalog-courses':(CourseCatalog.objects.filter(owning_department__campus__institution=programme.department.campus.institution,is_active=True),lambda r:r.course_code,'courses'),
                'enrolments':(StudentProgrammeEnrolment.objects.filter(programme=programme,enrolment_status='ACTIVE').select_related('student'),lambda r:r.student.student_number,'students'),
                'rooms':(Room.objects.filter(building__campus=programme.department.campus,is_active=True),lambda r:r.room_code,'rooms'),
            }
            if resource not in resources: raise NotFound()
            qs,label,limit_key=resources[resource]
            if not actor.is_superuser and limit_key:
                condition=None
                for limits in s.covering_grants(actor,programme):
                    from django.db.models import Q
                    item=Q(**{('student_id' if resource=='enrolments' else 'pk')+'__in':limits[limit_key]}) if limit_key in limits else Q()
                    condition=item if condition is None else condition|item
                    if limit_key not in limits: condition=Q();break
                qs=qs.filter(condition) if condition is not None else qs.none()
        pager=BoundedPagination();rows=pager.paginate_queryset(qs.order_by('pk'),request)
        return pager.get_paginated_response([{'id':str(row.pk),'label':label(row),'version':getattr(row,'version',None)} for row in rows])


class Reconciliation(RegistrationView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        from .operations import reconcile
        return Response(reconcile(request.user,read_action(request.user)))

class Detail(Records):
    @extend_schema(responses=OpenApiTypes.OBJECT,operation_id='registration_record_detail')
    def get(self,request,resource,pk):
        return super().get(request,resource,pk)


class ImportParse(RegistrationView):
    @extend_schema(request=OpenApiTypes.OBJECT,responses=OpenApiTypes.OBJECT)
    def post(self,request):
        from .operations import parse_csv
        if not permitted(request.user,'manage_registration'): raise PermissionDenied()
        if not isinstance(request.data,dict) or set(request.data)!={'content'} or not isinstance(request.data['content'],str):
            raise ValidationError('Supply a CSV content string only.')
        return Response({'rows':parse_csv(request.data['content'])})


class PersonalOfferings(RegistrationView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self,request):
        pager=BoundedPagination()
        page=pager.paginate_queryset(s.personal_offerings(request.user).order_by('pk'),request)
        return pager.get_paginated_response([{'id':str(row.pk),'label':s.record(row)['label']} for row in page])
