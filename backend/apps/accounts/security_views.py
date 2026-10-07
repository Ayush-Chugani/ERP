from django.conf import settings
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError
from django.core.exceptions import ValidationError as ModelValidationError
from drf_spectacular.utils import extend_schema
from apps.identity_access.security import change_password, reset_password, configure_mfa
from .views import CookieView, clear_refresh

class PasswordChangeInput(serializers.Serializer):
    current_password=serializers.CharField(write_only=True,trim_whitespace=False)
    new_password=serializers.CharField(write_only=True,trim_whitespace=False)
    mfa=serializers.CharField(write_only=True,required=False,max_length=500)

class PasswordChange(APIView):
    @extend_schema(request=PasswordChangeInput,responses={204:None})
    def post(self,request):
        if not settings.IDENTITY_ACCESS_SECURITY_ENABLED: raise NotFound()
        data=PasswordChangeInput(data=request.data); data.is_valid(raise_exception=True)
        try: change_password(actor=request.user,**data.validated_data)
        except ModelValidationError as exc: raise ValidationError(exc.messages)
        response=clear_refresh(Response(status=204)); response['Cache-Control']='no-store'
        return response

class PasswordResetInput(serializers.Serializer):
    user_id=serializers.IntegerField(min_value=1)
    token=serializers.CharField(write_only=True,max_length=200)
    new_password=serializers.CharField(write_only=True,trim_whitespace=False)
    mfa=serializers.CharField(write_only=True,required=False,max_length=500)

class PasswordReset(CookieView):
    @extend_schema(request=PasswordResetInput,responses={204:None})
    def post(self,request):
        if not settings.IDENTITY_ACCESS_SECURITY_ENABLED: raise NotFound()
        data=PasswordResetInput(data=request.data); data.is_valid(raise_exception=True)
        try: reset_password(**data.validated_data)
        except ModelValidationError as exc: raise ValidationError(exc.messages)
        return clear_refresh(Response(status=204))
