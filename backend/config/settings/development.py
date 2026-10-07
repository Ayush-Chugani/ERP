from .base import *
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
CSRF_TRUSTED_ORIGINS = [*CORS_ALLOWED_ORIGINS, "http://127.0.0.1:4173", "http://localhost:4173"]

AUTH_COOKIE_SECURE = False
CORS_ALLOW_CREDENTIALS = True
