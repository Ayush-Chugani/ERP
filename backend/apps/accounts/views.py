from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.middleware.csrf import CsrfViewMiddleware, get_token, rotate_token
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed
from rest_framework.throttling import AnonRateThrottle
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from drf_spectacular.utils import extend_schema

class LoginSerializer(serializers.Serializer):
    username=serializers.CharField(max_length=150)
    password=serializers.CharField(write_only=True, trim_whitespace=False)
    mfa=serializers.CharField(write_only=True, required=False, max_length=500)
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["Unexpected login fields."]})
        return super().to_internal_value(data)

class AccessSerializer(serializers.Serializer):
    access=serializers.CharField()

class LoginResponseSerializer(AccessSerializer):
    csrfToken=serializers.CharField()

class MeSerializer(serializers.Serializer):
    user_id=serializers.IntegerField()
    username=serializers.CharField()
    groups=serializers.ListField(child=serializers.CharField())
    permissions=serializers.ListField(child=serializers.CharField())
    access_modules=serializers.ListField(child=serializers.CharField())
    is_superuser=serializers.BooleanField()
    must_change_password=serializers.BooleanField()

class LoginThrottle(AnonRateThrottle):
    scope="login"

class CookieView(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    def get_authenticate_header(self, request):
        return "Bearer"
    def initial(self, request, *args, **kwargs):
        super().initial(request,*args,**kwargs)
        if request.method in ("POST","PUT","PATCH","DELETE"):
            raw=request._request
            origin=request.headers.get("Origin")
            allowed={f"{request.scheme}://{request.get_host()}", *settings.CSRF_TRUSTED_ORIGINS}
            if not origin or origin not in allowed:
                raise PermissionDenied("Origin verification failed.")
            check=CsrfViewMiddleware(lambda r: None)
            check.process_request(raw)
            # APIView dispatch is exempt; check an explicitly non-exempt callback.
            if check.process_view(raw, lambda r: None, (), {}):
                raise PermissionDenied("CSRF verification failed.")
    def finalize_response(self, request, response, *args, **kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response["Cache-Control"]="no-store"
        return response

class Csrf(CookieView):
    @extend_schema(responses=dict)
    def get(self, request):
        return Response({"csrfToken":get_token(request._request)})

def set_refresh(response, token):
    response.set_cookie(settings.AUTH_REFRESH_COOKIE, str(token),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        secure=settings.AUTH_COOKIE_SECURE, httponly=True, samesite="Strict", path="/api/v1/auth/")

def clear_refresh(response):
    # Match path/SameSite and preserve security flags on the deletion cookie.
    response.set_cookie(settings.AUTH_REFRESH_COOKIE,"",max_age=0,expires="Thu, 01 Jan 1970 00:00:00 GMT",
        path="/api/v1/auth/",secure=settings.AUTH_COOKIE_SECURE,httponly=True,samesite="Strict")
    return response

def cookie_token(request):
    value=request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
    if not value:
        raise AuthenticationFailed("Authentication required.")
    try:
        return RefreshToken(value)
    except TokenError:
        raise AuthenticationFailed("Authentication required.")

class Login(CookieView):
    throttle_classes=[LoginThrottle]
    @extend_schema(request=LoginSerializer, responses=LoginResponseSerializer)
    def post(self, request):
        serializer=LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data=dict(serializer.validated_data)
        if settings.IDENTITY_ACCESS_SECURITY_ENABLED:
            from apps.identity_access.security import login, token_claims
            user, session_id=login(**data, ip=request.META.get('REMOTE_ADDR'), user_agent=request.META.get('HTTP_USER_AGENT'))
        else:
            data.pop('mfa', None)
            user=authenticate(request=request._request, **data)
        if user is None or not user.is_active:
            raise AuthenticationFailed("Invalid username or password.")
        token=RefreshToken.for_user(user)
        if settings.IDENTITY_ACCESS_SECURITY_ENABLED:
            token_claims(user, token, session_id)
        rotate_token(request._request)
        response=Response({"access":str(token.access_token),"csrfToken":get_token(request._request)})
        set_refresh(response,token)
        return response

class Refresh(CookieView):
    @extend_schema(request=None,responses=AccessSerializer)
    def post(self, request):
        try:
            token=cookie_token(request)
            with transaction.atomic():
                # Recheck after locking: parallel consumption must not mint two tokens.
                OutstandingToken.objects.select_for_update().get(jti=token["jti"])
                token.check_blacklist()
                user=get_user_model().objects.get(pk=token["user_id"],is_active=True)
                if settings.IDENTITY_ACCESS_SECURITY_ENABLED:
                    from apps.identity_access.security import validate_session
                    validate_session(user, token)
                    if user.must_change_password:
                        raise AuthenticationFailed('Password change required.')
                token.blacklist()
                replacement=RefreshToken.for_user(user)
                if settings.IDENTITY_ACCESS_SECURITY_ENABLED:
                    from apps.identity_access.security import token_claims
                    token_claims(user, replacement, token.get('session_id'))
        except (TokenError, OutstandingToken.DoesNotExist, get_user_model().DoesNotExist, AuthenticationFailed):
            return clear_refresh(Response({"error":{"code":"not_authenticated","message":"Authentication required.","details":{}}},status=401))
        response=Response({"access":str(replacement.access_token)})
        set_refresh(response,replacement)
        return response

class Logout(CookieView):
    @extend_schema(request=None,responses={204:None})
    def post(self, request):
        try:
            token=cookie_token(request)
            with transaction.atomic():
                OutstandingToken.objects.select_for_update().get(jti=token["jti"])
                token.blacklist()
                if settings.IDENTITY_ACCESS_SECURITY_ENABLED:
                    from apps.identity_access.security import logout_session
                    actor=get_user_model().objects.filter(pk=token['user_id']).first()
                    logout_session(actor=actor,session_id=token.get('session_id'))
        except (TokenError, AuthenticationFailed, OutstandingToken.DoesNotExist):
            pass
        return clear_refresh(Response(status=204))

def access_modules(user):
    """IAM module codes (e.g. AWARDS, ATTENDANCE) the user holds an ALLOW permission for.

    Used only to decide which navigation entries to show; every endpoint still
    enforces its own scoped permission check.
    """
    if user.is_superuser:
        return []
    from django.db.models import Q
    from django.utils import timezone
    from apps.identity_access.models import RolePermission, UserRoleAssignment
    now = timezone.now()
    roles = UserRoleAssignment.objects.filter(user=user, assignment_status="ACTIVE", valid_from__lte=now).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gt=now)).values("role_id")
    codes = RolePermission.objects.filter(role_id__in=roles, permission_effect="ALLOW").values_list(
        "permission__permission_code", flat=True)
    return sorted({code.split(".", 1)[0] for code in codes})

class Me(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        user=request.user
        response=Response({"user_id":user.pk,"username":user.username,
            "groups":list(user.groups.values_list("name",flat=True)),
            "permissions":sorted(user.get_all_permissions()),"access_modules":access_modules(user),"is_superuser":user.is_superuser,"must_change_password":settings.IDENTITY_ACCESS_SECURITY_ENABLED and user.must_change_password})
        response["Cache-Control"]="no-store"
        return response
