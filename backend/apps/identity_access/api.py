from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms.models import model_to_dict
from django.urls import path
from django.utils import timezone
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from drf_spectacular.utils import extend_schema
from apps.core.pagination import BoundedPagination
from . import models as m, services
from .evaluator import has_permission, Scope, evidence, effective_effect
from .audit import record

class SecurityMutationThrottle(UserRateThrottle):
    scope="security_mutation"

class SecureView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request,*args,**kwargs)
        if not settings.IDENTITY_ACCESS_ENABLED: raise NotFound()
        if request.user.must_change_password: raise PermissionDenied('Password change required.')
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response['Cache-Control']='no-store'
        return response

class SecurityContext(SecureView):
    @extend_schema(responses=dict)
    def get(self,request):
        support=m.ImpersonationSession.objects.filter(actor=request.user,ended_at__isnull=True,expires_at__gt=timezone.now()).first()
        return Response({'support_session':{'session_id':str(support.pk),'target_user_id':support.target_id,'expires_at':support.expires_at} if support else None,'user_id':request.user.pk,'staged':True,
            'can_administer':has_permission(request.user,'IAM.ALL.READ','GLOBAL',0),
            'can_audit':has_permission(request.user,'AUDIT.ALL.READ','GLOBAL',0),
            'must_change_password':request.user.must_change_password,
            'multi_factor_enabled':request.user.multi_factor_enabled})

# Explicit field allowlists, including for user identities and audit output.
RESOURCES={
 'users':(get_user_model(),['user_id','username','email','account_status','must_change_password','multi_factor_enabled','locked_until']),
 'modules':(m.AccessModule,['access_module_id','module_code','module_name','is_active']),
 'resources':(m.AccessResource,['access_resource_id','access_module_id','resource_code','resource_name','is_active']),
 'actions':(m.AccessAction,['access_action_id','action_code','action_name','is_active']),
 'permissions':(m.Permission,['permission_id','permission_code','permission_name','is_sensitive','is_active']),
 'roles':(m.Role,['role_id','parent_role_id','role_code','role_name','role_category','role_level','description','is_system_role','is_assignable','is_active']),
 'role-permissions':(m.RolePermission,['role_id','permission_id','permission_effect']),
 'assignments':(m.UserRoleAssignment,['user_role_assignment_id','user_id','role_id','scope_type','scope_entity_id','valid_from','valid_to','assignment_status','assignment_reason']),
 'overrides':(m.UserPermissionOverride,['user_permission_override_id','user_id','permission_id','scope_type','scope_entity_id','permission_effect','valid_from','valid_to','revoked_at','justification']),
 'delegations':(m.RoleDelegation,['role_delegation_id','delegator_user_id','delegate_user_id','source_assignment_id','valid_from','valid_to','delegation_status','reason']),
 'student-links':(m.StudentUserAccount,['student_id','user_id','linked_at']),
 'employee-links':(m.EmployeeUserAccount,['employee_id','user_id','linked_at']),
 'login-audit':(m.LoginAudit,['login_audit_id','user_id','username_attempted','login_at','logout_at','ip_address','was_successful','failure_reason','session_identifier']),
 'activity-audit':(m.ActivityAudit,['activity_audit_id','user_id','module_code','action_code','entity_name','entity_id','activity_at','ip_address','request_identifier','before_values','after_values','details']),
}
FILTERS={'user_id','role_id','permission_id','scope_type','assignment_status','delegation_status','permission_effect','module_code','action_code','entity_name','entity_id','request_identifier','session_identifier','username_attempted','ip_address','was_successful'}

class Catalogue(SecureView):
    @extend_schema(responses=dict)
    def get(self,request,resource):
        if resource not in RESOURCES: raise NotFound()
        module='AUDIT' if resource.endswith('-audit') else 'IAM'
        if not has_permission(request.user,f'{module}.ALL.READ','GLOBAL',0): raise PermissionDenied()
        model,fields=RESOURCES[resource]; query=model.objects.all().order_by('pk')
        for key in FILTERS & set(fields):
            if key in request.query_params:
                value=request.query_params[key]
                if key.endswith('_id') and key not in ('entity_id',):
                    try: value=int(value)
                    except ValueError: raise ValidationError('Invalid identifier filter.')
                if key=='was_successful':
                    if value not in ('true','false'): raise ValidationError('Invalid boolean filter.')
                    value=value=='true'
                query=query.filter(**{key:value})
        if resource.endswith('-audit'):
            date='login_at' if resource=='login-audit' else 'activity_at'
            for parameter,lookup in [('from_date','gte'),('to_date','lt')]:
                if parameter in request.query_params:
                    value=serializers.DateTimeField().run_validation(request.query_params[parameter])
                    query=query.filter(**{date+'__'+lookup:value})
        paginator=BoundedPagination(); rows=paginator.paginate_queryset(query.values(*fields),request)
        return paginator.get_paginated_response(rows)

class Proof(serializers.Serializer):
    password=serializers.CharField(write_only=True,trim_whitespace=False)
    mfa=serializers.CharField(write_only=True,required=False,max_length=500)

class CommandInput(serializers.Serializer):
    command=serializers.ChoiceField(choices=['assign_role','end_assignment','grant_override','end_override','request_delegation','transition_delegation','save_role','set_matrix','save_user','transition_assignment'])
    proof=Proof(write_only=True)
    justification=serializers.CharField(max_length=500)
    values=serializers.DictField()

# Field validation is deliberately per command; unsupported arguments never reach services.
ID=lambda:serializers.IntegerField(min_value=1)
DATE=lambda:serializers.DateTimeField()
SCOPES=['GLOBAL','INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME','SELF']
COMMAND_FIELDS={
 'transition_assignment':{'pk':ID(),'status':serializers.ChoiceField(choices=['ACTIVE','SUSPENDED','REVOKED'])},
 'save_user':{'pk':serializers.IntegerField(min_value=1,required=False),'values':serializers.DictField()},
 'assign_role':{'user_id':ID(),'role_id':ID(),'scope_type':serializers.ChoiceField(choices=SCOPES),'entity_id':serializers.IntegerField(min_value=0),'valid_from':DATE(),'valid_to':serializers.DateTimeField(allow_null=True,required=False)},
 'end_assignment':{'pk':ID()},
 'grant_override':{'user_id':ID(),'permission_id':ID(),'scope_type':serializers.ChoiceField(choices=SCOPES),'entity_id':serializers.IntegerField(min_value=0),'effect':serializers.ChoiceField(choices=['ALLOW','DENY']),'valid_from':DATE(),'valid_to':serializers.DateTimeField(allow_null=True)},
 'end_override':{'pk':ID()},
 'request_delegation':{'source_assignment_id':ID(),'delegate_user_id':ID(),'valid_from':DATE(),'valid_to':DATE()},
 'transition_delegation':{'pk':ID(),'status':serializers.ChoiceField(choices=['ACTIVE','REVOKED'])},
 'save_role':{'pk':serializers.IntegerField(min_value=1,required=False),'values':serializers.DictField()},
 'set_matrix':{'role_id':ID(),'entries':serializers.ListField(child=serializers.DictField(),max_length=220)},
}

class Commands(SecureView):
    throttle_classes=[SecurityMutationThrottle]
    @extend_schema(request=CommandInput,responses=dict)
    def post(self,request):
        from django.core.exceptions import ValidationError as ModelValidationError, ObjectDoesNotExist
        from django.db import IntegrityError
        data=CommandInput(data=request.data); data.is_valid(raise_exception=True); data=dict(data.validated_data)
        command=data.pop('command'); values=data.pop('values'); fields=COMMAND_FIELDS[command]
        if set(values)-set(fields): raise ValidationError('Unsupported command fields.')
        validator=type('CommandValues',(serializers.Serializer,),fields)(data=values)
        validator.is_valid(raise_exception=True)
        try:
            obj=getattr(services,command)(actor=request.user,**data,**validator.validated_data)
        except ObjectDoesNotExist: raise NotFound()
        except ModelValidationError as exc: raise ValidationError(exc.messages)
        except (IntegrityError,ValueError,KeyError,TypeError): raise ValidationError('Invalid or conflicting security command.')
        return Response({'id':obj.pk},status=200)

class ExplainInput(serializers.Serializer):
    user_id=ID()
    permission_code=serializers.CharField(max_length=150)
    scope_type=serializers.ChoiceField(choices=SCOPES)
    entity_id=serializers.IntegerField(min_value=0)

class Explain(SecureView):
    @extend_schema(request=ExplainInput,responses=dict)
    def post(self,request):
        if not has_permission(request.user,'IAM.ALL.READ','GLOBAL',0): raise PermissionDenied()
        data=ExplainInput(data=request.data);data.is_valid(raise_exception=True);v=data.validated_data
        user=get_user_model().objects.filter(pk=v['user_id']).first()
        if not user: raise NotFound()
        try: scope=Scope(v['scope_type'],v['entity_id'])
        except ValueError: raise ValidationError('Invalid scope.')
        rows=[{**row,'scope':{'type':row['scope'].kind,'entity_id':row['scope'].entity_id}} for row in evidence(user,v['permission_code']) if row['scope']==scope]
        return Response({'effect':effective_effect(user,v['permission_code'],[scope]),'sources':rows})

class SupportInput(serializers.Serializer):
    target_id=ID()
    proof=Proof(write_only=True)
    justification=serializers.CharField(max_length=500)

class SupportSession(SecureView):
    throttle_classes=[SecurityMutationThrottle]
    @extend_schema(request=SupportInput,responses=dict)
    def post(self,request):
        from .impersonation import start
        data=SupportInput(data=request.data);data.is_valid(raise_exception=True)
        from django.core.exceptions import ObjectDoesNotExist
        try: row=start(actor=request.user,**data.validated_data)
        except ObjectDoesNotExist: raise NotFound()
        return Response({'session_id':str(row.pk),'original_actor_id':row.actor_id,'target_user_id':row.target_id,'expires_at':row.expires_at,'read_only':True})

class SupportDetail(SecureView):
    @extend_schema(responses=dict)
    def get(self,request,session_id):
        from .impersonation import context
        row=context(actor=request.user,session_id=session_id)
        return Response({'session_id':str(row.pk),'original_actor_id':row.actor_id,'target_user_id':row.target_id,'expires_at':row.expires_at,'read_only':True})
    @extend_schema(request=None,responses={204:None})
    def delete(self,request,session_id):
        from .impersonation import end
        end(actor=request.user,session_id=session_id)
        return Response(status=204)

class ExportInput(serializers.Serializer):
    resource=serializers.ChoiceField(choices=['login-audit','activity-audit'])
    proof=Proof(write_only=True)
    from_date=serializers.DateTimeField()
    to_date=serializers.DateTimeField()

class AuditExport(SecureView):
    @extend_schema(request=ExportInput,responses=bytes)
    def post(self,request):
        import csv,io
        from django.http import HttpResponse
        from .security import step_up
        data=ExportInput(data=request.data);data.is_valid(raise_exception=True);v=data.validated_data
        if not has_permission(request.user,'AUDIT.ALL.EXPORT','GLOBAL',0): raise PermissionDenied()
        step_up(request.user,v['proof'])
        if v['to_date']<=v['from_date']: raise ValidationError('Invalid date interval.')
        model,fields=RESOURCES[v['resource']]; date='login_at' if v['resource']=='login-audit' else 'activity_at'
        query=model.objects.filter(**{date+'__gte':v['from_date'],date+'__lt':v['to_date']}).order_by('pk')
        rows=list(query.values_list(*fields)[:10001])
        if len(rows)>10000: raise ValidationError('Narrow the date interval to at most 10000 records.')
        output=io.StringIO();writer=csv.writer(output);writer.writerow(fields)
        def cell(value):
            text='' if value is None else str(value)
            return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
        for row in rows: writer.writerow([cell(value) for value in row])
        record(actor=request.user,action='EXPORT',module='AUDIT',details={'resource':v['resource'],'count':len(rows)})
        response=HttpResponse(output.getvalue(),content_type='text/csv')
        response['Content-Disposition']='attachment; filename="security-audit.csv"'
        return response

urlpatterns=[path('support-sessions/',SupportSession.as_view()),path('support-sessions/<uuid:session_id>/',SupportDetail.as_view()),path('audit-export/',AuditExport.as_view()),path('context/',SecurityContext.as_view()),path('commands/',Commands.as_view()),path('explain/',Explain.as_view()),path('<str:resource>/',Catalogue.as_view())]
