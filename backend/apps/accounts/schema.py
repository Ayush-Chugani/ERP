from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme

class SecurityJWTScheme(SimpleJWTScheme):
    target_class='apps.accounts.authentication.SecurityJWTAuthentication'
    name='jwtAuth'
