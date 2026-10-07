from .base import *
ALLOWED_HOSTS = [host.strip() for host in required("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()]
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Wildcard production hosts are not allowed")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SIMS_HSTS_SUBDOMAINS", "0") == "1"
SECURE_HSTS_PRELOAD = os.getenv("SIMS_HSTS_PRELOAD", "0") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Backend must only be reachable through the trusted proxy that overwrites this header.

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576
