from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


class SecurityJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None or not settings.IDENTITY_ACCESS_SECURITY_ENABLED:
            return result
        user, token = result
        from apps.identity_access.security import validate_session
        validate_session(user, token)
        if user.must_change_password and request.path not in ('/api/v1/auth/password/change/', '/api/v1/auth/me/'):
            raise PermissionDenied('Password change required.')
        return result
