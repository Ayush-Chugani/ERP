import os
from pathlib import Path
from dotenv import load_dotenv

# Read local credentials before supplying isolated-test defaults.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-for-deployment-" * 3)
os.environ.setdefault("SIMS_DB_PASSWORD", "test-only")
from .base import *
# SQLite is opt-in for foundation tests, never a substitute for MySQL schema tests.
if os.getenv("SIMS_TEST_SQLITE") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

AUTH_COOKIE_SECURE = False
