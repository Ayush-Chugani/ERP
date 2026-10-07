from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from . import models as m, serializers as z, services as s
from .policies import allowed, scoped


VERSION = OpenApiParameter('If-Match',str,OpenApiParameter.HEADER,required=True,description='Current integer record version.')


def version(request):
    value=request.headers.get('If-Match','').strip('"')
    if not value.isdigit():
        raise ValidationError({'If-Match':'Current integer version is required.'})
    return value


def validated(cls,request):
    if set(request.data)-set(cls().fields):
        raise ValidationError('Unsupported fields.')
    serializer=cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@extend_schema(parameters=[OpenApiParameter('id',str,OpenApiParameter.PATH,description='Record identifier.')])
class ReadView(mixins.ListModelMixin,mixins.RetrieveModelMixin,viewsets.GenericViewSet):
    model=None
    filter_fields=()
    search_fields=()
    ordering_fields=('pk',)

    def get_queryset(self):
        if getattr(self,'swagger_fake_view',False):
            return self.model.objects.none()
        if not allowed(self.request.user,'view',self.model):
            raise PermissionDenied()
        qs=scoped(self.model,self.request.user)
        qs=qs.select_related(*[f.name for f in self.model._meta.fields if f.is_relation])
        for name in self.filter_fields:
            if name in self.request.query_params:
                value=self.request.query_params[name]
                if name.endswith('_id') and not value.isdigit():
                    raise ValidationError({name:'Supply a positive integer.'})
                qs=qs.filter(**{name:value})
        search=self.request.query_params.get('search','').strip()
        if len(search)>100:
            raise ValidationError('Search is limited to 100 characters.')
        if search and self.search_fields:
            predicate=Q(pk__in=[])
            for field in self.search_fields:
                predicate |= Q(**{field+'__istartswith':search})
            qs=qs.filter(predicate)
        order=self.request.query_params.get('ordering','pk')
        if order.lstrip('-') not in self.ordering_fields:
            raise ValidationError('Unsupported ordering.')
        return qs.order_by(order,'pk')


class WritableView(ReadView):
    def create(self,request):
        data=validated(self.serializer_class,request)
        obj=s.save_record(actor=request.user,model=self.model,values=data)
        return Response(self.get_serializer(obj).data,status=201)

    @extend_schema(parameters=[VERSION])
    def partial_update(self,request,pk=None):
        serializer=self.get_serializer(data=request.data,partial=True)
        serializer.is_valid(raise_exception=True)
        obj=s.save_record(actor=request.user,model=self.model,pk=pk,version=version(request),values=serializer.validated_data)
        return Response(self.get_serializer(obj).data)


class Applicants(WritableView):
    model=m.AdmissionApplicant
    serializer_class=z.ApplicantSerializer
    filter_fields=('institution_id',)
    search_fields=('display_name',)
    ordering_fields=('pk','display_name','created_at')

    @extend_schema(responses=z.ApplicantSerializer(many=True))
    @action(detail=True,methods=['get'],url_path='duplicate-candidates')
    def duplicates(self,request,pk=None):
        self.get_object()
        from .selectors import duplicate_candidates
        rows=duplicate_candidates(actor=request.user,applicant_id=pk)
        return Response(self.get_serializer(rows,many=True).data)


class Applications(WritableView):
    model=m.AdmissionApplication
    serializer_class=z.ApplicationSerializer
    filter_fields=('programme_id','academic_year_id','application_status','eligibility_status','admission_applicant_id')
    search_fields=('application_number',)
    ordering_fields=('pk','application_date','created_at')

    @extend_schema(request=z.TransitionSerializer,responses=z.ApplicationSerializer,parameters=[VERSION])
    @action(detail=True,methods=['post'])
    def transition(self,request,pk=None):
        obj=s.transition_application(actor=request.user,pk=pk,version=version(request),**validated(z.TransitionSerializer,request))
        return Response(self.get_serializer(obj).data)

    @extend_schema(request=z.ClearanceSerializer,parameters=[VERSION],responses={201:None})
    @action(detail=True,methods=['post'],url_path='fee-clearance')
    def clearance(self,request,pk=None):
        s.record_clearance(actor=request.user,pk=pk,version=version(request),**validated(z.ClearanceSerializer,request))
        return Response(status=201)

    @extend_schema(request=z.AdmitSerializer,responses=z.EnrolmentSerializer,parameters=[VERSION,OpenApiParameter('Idempotency-Key',str,OpenApiParameter.HEADER,required=True)])
    @action(detail=True,methods=['post'])
    def admit(self,request,pk=None):
        obj=s.admit_application(actor=request.user,application_id=pk,version=version(request),payload=validated(z.AdmitSerializer,request),idempotency_key=request.headers.get('Idempotency-Key'))
        return Response(z.EnrolmentSerializer(obj).data)


class Enrolments(ReadView):
    model=m.StudentProgrammeEnrolment
    serializer_class=z.EnrolmentSerializer
    filter_fields=('programme_id','student_id','admission_academic_year_id','enrolment_status')

    @extend_schema(request=z.LifecycleSerializer,responses=z.EnrolmentSerializer,parameters=[VERSION])
    @action(detail=True,methods=['post'])
    def transition(self,request,pk=None):
        obj=s.transition_enrolment(actor=request.user,pk=pk,version=version(request),**validated(z.LifecycleSerializer,request))
        return Response(self.get_serializer(obj).data)


class History(ReadView):
    model=m.EnrolmentStatusHistory
    serializer_class=z.HistorySerializer
    filter_fields=('enrolment_id',)
    ordering_fields=('pk','effective_date','sequence_number')
