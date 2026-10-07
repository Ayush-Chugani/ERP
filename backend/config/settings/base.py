import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)
def required(name):
    value = os.environ.get(name)
    if not value or value.startswith("replace-"):
        raise ImproperlyConfigured(f"Set {name} in the environment")
    return value
SECRET_KEY = required("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = []
INSTALLED_APPS = [
    'apps.feedback',
    'apps.student_support',
    'apps.documents_exit',
    'apps.assessments_results',
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "drf_spectacular", "django_filters",
    "rest_framework_simplejwt.token_blacklist",
    "apps.people_master.apps.PeopleMasterConfig",
    "apps.admission_enrolment.apps.AdmissionEnrolmentConfig",
    "apps.term_registration.apps.TermRegistrationConfig",
    "apps.teaching_timetable.apps.TeachingTimetableConfig",
    "apps.attendance_lesson_plan.apps.AttendanceLessonPlanConfig",
    "apps.core.apps.CoreConfig", "apps.accounts", "apps.common_reference",
    "apps.organization", "apps.tenancy", "apps.academic_calendar.apps.AcademicCalendarConfig", "apps.curriculum_catalog.apps.CurriculumCatalogConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.SecurityModelBackend']
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql", "NAME": os.getenv("SIMS_DB_NAME", "sims_reference_dev"),
    "USER": os.getenv("SIMS_DB_USER", "root"), "PASSWORD": required("SIMS_DB_PASSWORD"),
    "HOST": os.getenv("SIMS_DB_HOST", "127.0.0.1"), "PORT": os.getenv("SIMS_DB_PORT", "3307"),
    "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5,
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION', time_zone='+00:00'"},
    "TEST": {"NAME": "test_sims_reference", "CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation." + name} for name in
    ["UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"]]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.SecurityJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.BoundedPagination", "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.errors.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SIMPLE_JWT = {"USER_ID_FIELD": "user_id", "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True}
SPECTACULAR_SETTINGS = {"TITLE": "SIMS API", "VERSION": "1.0.0", "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"]}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
DISPLAY_TIME_ZONE = os.getenv("SIMS_DISPLAY_TIME_ZONE", "UTC")
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = []
CORS_URLS_REGEX = r"^/api/.*$"

AUTH_REFRESH_COOKIE = "sims_refresh"
AUTH_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = []
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = True
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=1)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"login": "5/min"}


# Calendar is installed independently from runtime module activation.
ACADEMIC_CALENDAR_ENABLED = os.getenv('SIMS_ACADEMIC_CALENDAR_ENABLED', '1') == '1'
import json
CALENDAR_CAMPUS_TIMEZONES = json.loads(os.getenv('SIMS_CALENDAR_CAMPUS_TIMEZONES', '{}'))

CURRICULUM_CATALOG_ENABLED = os.getenv("SIMS_CURRICULUM_CATALOG_ENABLED", "1") == "1"
CURRICULUM_GRADE_CODES = tuple(value.strip().upper() for value in os.getenv("SIMS_CURRICULUM_GRADE_CODES", "").split(",") if value.strip())

# M5 global switch; institution grants remain separately required.
PEOPLE_MASTER_ENABLED = os.getenv("SIMS_PEOPLE_MASTER_ENABLED", "1") == "1"
ADMISSION_ENROLMENT_ENABLED = os.getenv('SIMS_ADMISSION_ENROLMENT_ENABLED', '0') == '1'
TERM_REGISTRATION_ENABLED = os.getenv('SIMS_TERM_REGISTRATION_ENABLED', '0') == '1'
TEACHING_TIMETABLE_ENABLED = os.getenv('SIMS_TEACHING_TIMETABLE_ENABLED', '0') == '1'

SPECTACULAR_SETTINGS.setdefault("ENUM_NAME_OVERRIDES", {})["AdmissionEnrolmentStatusEnum"] = [(value, value.replace("_", " ").title()) for value in ("ACTIVE", "ON_BREAK", "WITHDRAWN", "TRANSFERRED", "COMPLETED", "TERMINATED")]

# Installed result/attempt/prerequisite provider; absence fails closed in M7.
REGISTRATION_ELIGIBILITY_ADAPTER = os.getenv('SIMS_REGISTRATION_ELIGIBILITY_ADAPTER', '')

ATTENDANCE_ENABLED = os.getenv('SIMS_ATTENDANCE_ENABLED', '0') == '1'
ATTENDANCE_CALENDAR_ADAPTER = os.getenv('SIMS_ATTENDANCE_CALENDAR_ADAPTER', '')

ASSESSMENTS_RESULTS_ENABLED = os.getenv('SIMS_ASSESSMENTS_RESULTS_ENABLED', '0') == '1'

FEEDBACK_ENABLED = os.getenv('SIMS_FEEDBACK_ENABLED', '0') == '1'
FEEDBACK_PRIVACY_KEY = os.getenv('SIMS_FEEDBACK_PRIVACY_KEY', '')

# M12 preserves the five canonical tables; rollout policies live in configuration.
STUDENT_SUPPORT_ENABLED = os.getenv('SIMS_STUDENT_SUPPORT_ENABLED', '0') == '1'
STUDENT_SUPPORT_INSTITUTIONS = [int(v) for v in os.getenv('SIMS_STUDENT_SUPPORT_INSTITUTIONS', '').split(',') if v.strip()]
import json as _support_json
STUDENT_SUPPORT_POLICIES = _support_json.loads(os.getenv('SIMS_STUDENT_SUPPORT_POLICIES', '{}'))
STUDENT_SUPPORT_NUMBER_PREFIX = os.getenv('SIMS_STUDENT_SUPPORT_NUMBER_PREFIX', 'GR')

SPECTACULAR_SETTINGS.setdefault('ENUM_NAME_OVERRIDES', {}).update({
    'SupportAssignmentStatusEnum': 'apps.student_support.policies.ASSIGNMENT',
    'SupportSessionStatusEnum': 'apps.student_support.policies.SESSION',
    'SupportGrievanceStatusEnum': 'apps.student_support.policies.STATUS',
})

DOCUMENTS_EXIT_ENABLED = os.getenv('SIMS_DOCUMENTS_EXIT_ENABLED','0') == '1'
DOCUMENTS_EXIT_INSTITUTIONS = [int(v) for v in os.getenv('SIMS_DOCUMENTS_EXIT_INSTITUTIONS','').split(',') if v.strip()]
DOCUMENTS_EXIT_POLICIES = _support_json.loads(os.getenv('SIMS_DOCUMENTS_EXIT_POLICIES','{}'))
DOCUMENTS_STORAGE_ROOT = Path(os.getenv('SIMS_DOCUMENTS_STORAGE_ROOT', str(BASE_DIR / 'private_documents')))
DOCUMENTS_STORAGE_FACTORY = os.getenv('SIMS_DOCUMENTS_STORAGE_FACTORY','apps.documents_exit.storage.LocalPrivateStorage')
DOCUMENTS_MAX_BYTES = int(os.getenv('SIMS_DOCUMENTS_MAX_BYTES','10485760'))
DOCUMENTS_ALLOWED_EXTENSIONS = ('pdf','png','jpg','jpeg')
DOCUMENTS_ALLOWED_MIMES = ('application/pdf','image/png','image/jpeg')
DOCUMENTS_MALWARE_SCANNER = os.getenv('SIMS_DOCUMENTS_MALWARE_SCANNER','')
DOCUMENTS_CERTIFICATE_RENDERER = os.getenv('SIMS_DOCUMENTS_CERTIFICATE_RENDERER','')
DOCUMENTS_EXIT_CLEARANCE = os.getenv('SIMS_DOCUMENTS_EXIT_CLEARANCE','')
DOCUMENTS_NUMBER_PREFIX = os.getenv('SIMS_DOCUMENTS_NUMBER_PREFIX','SIMS')

SPECTACULAR_SETTINGS.setdefault('ENUM_NAME_OVERRIDES', {}).update({
    'DocumentVerificationEnum':'apps.documents_exit.models.Verification.choices',
    'CertificateRequestStatusEnum':'apps.documents_exit.models.RequestStatus.choices',
    'StudentExitTypeEnum':'apps.documents_exit.models.ExitType.choices',
})

# Parser diagnostics can contain untrusted file tokens. Only sanitized M13 errors leave the parser boundary.
LOGGING = {'version':1,'disable_existing_loggers':False,'handlers':{'private_document_parser':{'class':'logging.NullHandler'}},'loggers':{'pypdf':{'handlers':['private_document_parser'],'propagate':False}}}

# M14 is opt-in per installation and institution.
INSTALLED_APPS += ["apps.communication"]
COMMUNICATION_ENABLED = os.getenv("SIMS_COMMUNICATION_ENABLED", "0") == "1"
COMMUNICATION_INSTITUTIONS = [int(x) for x in os.getenv("SIMS_COMMUNICATION_INSTITUTIONS", "").split(",") if x.strip()]

# M15 is staged: installation does not replace existing module authorization.
INSTALLED_APPS += ['apps.identity_access']
IDENTITY_ACCESS_ENABLED = os.getenv('SIMS_IDENTITY_ACCESS_ENABLED', '0') == '1'
IDENTITY_ACCESS_SECURITY_ENABLED = os.getenv('SIMS_IDENTITY_ACCESS_SECURITY_ENABLED', '0') == '1'
IDENTITY_ACCESS_LOGIN_LIMIT = 5
IDENTITY_ACCESS_LOCK_SECONDS = 900
IDENTITY_ACCESS_PASSWORD_HISTORY = 5
IDENTITY_ACCESS_MFA_PROVIDER = os.getenv('SIMS_IDENTITY_ACCESS_MFA_PROVIDER', '')

REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['security_mutation']='10/min'

# M16 installation is separate from operational activation.
INSTALLED_APPS += ['apps.employee_hr.apps.EmployeeHrConfig']
EMPLOYEE_HR_ENABLED = os.getenv('SIMS_EMPLOYEE_HR_ENABLED', '0') == '1'

# HR secrets are supplied by deployment configuration; no generated/default keys.
EMPLOYEE_HR_ENCRYPTION_KEYS = json.loads(os.getenv('SIMS_EMPLOYEE_HR_ENCRYPTION_KEYS','{}'))
EMPLOYEE_HR_ACTIVE_KEY_VERSION = int(os.getenv('SIMS_EMPLOYEE_HR_ACTIVE_KEY_VERSION','0'))
EMPLOYEE_HR_FINGERPRINT_KEY = os.getenv('SIMS_EMPLOYEE_HR_FINGERPRINT_KEY','')

# Shared staff research schema; operational endpoints are not enabled.
INSTALLED_APPS += ['apps.staff_profile.apps.StaffProfileConfig', 'apps.staff_activities.apps.StaffActivitiesConfig', 'apps.research_publications.apps.ResearchPublicationsConfig']

INSTALLED_APPS += ['apps.conferences.apps.ConferencesConfig']
CONFERENCES_ENABLED = os.getenv('SIMS_CONFERENCES_ENABLED', '0') == '1'

CONFERENCES_CONTRIBUTION_REQUIREMENTS = json.loads(os.getenv('SIMS_CONFERENCES_CONTRIBUTION_REQUIREMENTS', '{}'))

INSTALLED_APPS += ["apps.faculty_internships"]
FACULTY_INTERNSHIPS_ENABLED = os.getenv("SIMS_FACULTY_INTERNSHIPS_ENABLED", "0") == "1"

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["faculty_internships"] = os.getenv("SIMS_FACULTY_INTERNSHIPS_RATE", "120/min")

INSTALLED_APPS += ["apps.research_proposals"]
RESEARCH_PROPOSALS_ENABLED = os.getenv("SIMS_RESEARCH_PROPOSALS_ENABLED", "0") == "1"
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["research_proposals"] = os.getenv("SIMS_RESEARCH_PROPOSALS_RATE", "120/min")

RESEARCH_PROPOSALS_EVENT_HANDLER = os.getenv("SIMS_RESEARCH_PROPOSALS_EVENT_HANDLER", "")

SPECTACULAR_SETTINGS.setdefault("ENUM_NAME_OVERRIDES", {})["StaffActivityWorkflowActionEnum"] = ["submit", "withdraw", "review", "return", "verify", "approve", "reject"]

INSTALLED_APPS += ["apps.funded_projects"]
FUNDED_PROJECTS_ENABLED = os.getenv("SIMS_FUNDED_PROJECTS_ENABLED", "0") == "1"
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["funded_projects"] = os.getenv("SIMS_FUNDED_PROJECTS_RATE", "120/min")
FUNDED_PROJECTS_CURRENCIES = tuple(os.getenv("SIMS_FUNDED_PROJECTS_CURRENCIES", "INR").split(","))

INSTALLED_APPS += ["apps.consultancy"]
CONSULTANCY_ENABLED = os.getenv("SIMS_CONSULTANCY_ENABLED", "0") == "1"
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["consultancy"] = os.getenv("SIMS_CONSULTANCY_RATE", "120/min")

INSTALLED_APPS += ["apps.cocurricular"]
COCURRICULAR_ENABLED = os.getenv("SIMS_COCURRICULAR_ENABLED", "0") == "1"
COCURRICULAR_EVENT_HANDLER = os.getenv("SIMS_COCURRICULAR_EVENT_HANDLER", "")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["cocurricular"] = os.getenv("SIMS_COCURRICULAR_RATE", "120/min")

INSTALLED_APPS += ["apps.extracurricular"]
EXTRACURRICULAR_ENABLED = os.getenv("SIMS_EXTRACURRICULAR_ENABLED", "0") == "1"
EXTRACURRICULAR_EVENT_HANDLER = os.getenv("SIMS_EXTRACURRICULAR_EVENT_HANDLER", "")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["extracurricular"] = os.getenv("SIMS_EXTRACURRICULAR_RATE", "120/min")

INSTALLED_APPS += ["apps.awards"]
AWARDS_ENABLED = os.getenv("SIMS_AWARDS_ENABLED", "0") == "1"
AWARDS_EVENT_HANDLER = os.getenv("SIMS_AWARDS_EVENT_HANDLER", "")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["awards"] = os.getenv("SIMS_AWARDS_RATE", "120/min")

INSTALLED_APPS += ["apps.professional_memberships"]
PROFESSIONAL_MEMBERSHIPS_ENABLED = os.getenv("SIMS_PROFESSIONAL_MEMBERSHIPS_ENABLED", "0") == "1"
PROFESSIONAL_MEMBERSHIPS_EVENT_HANDLER = os.getenv("SIMS_PROFESSIONAL_MEMBERSHIPS_EVENT_HANDLER", "")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["professional_memberships"] = os.getenv("SIMS_PROFESSIONAL_MEMBERSHIPS_RATE", "120/min")
MEMBERSHIPS_RENEWAL_WINDOW_DAYS = int(os.getenv("SIMS_MEMBERSHIPS_RENEWAL_WINDOW_DAYS", "30"))
MEMBERSHIPS_AUTO_EXPIRY_ENABLED = os.getenv("SIMS_MEMBERSHIPS_AUTO_EXPIRY_ENABLED", "0") == "1"

INSTALLED_APPS += ["apps.professional_contributions"]
PROFESSIONAL_CONTRIBUTIONS_ENABLED = os.getenv("SIMS_PROFESSIONAL_CONTRIBUTIONS_ENABLED", "0") == "1"
PROFESSIONAL_CONTRIBUTIONS_EVENT_HANDLER = os.getenv("SIMS_PROFESSIONAL_CONTRIBUTIONS_EVENT_HANDLER", "")
PROFESSIONAL_CONTRIBUTIONS_TYPE_RULES = {}
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["professional_contributions"] = "120/min"

# M33 uses M13 private storage, upload limits and required scanner settings.
INSTALLED_APPS += ["apps.evidence"]
EVIDENCE_ENABLED = os.getenv("SIMS_EVIDENCE_ENABLED", "0") == "1"
EVIDENCE_ALLOW_SELF_VERIFY = os.getenv("SIMS_EVIDENCE_ALLOW_SELF_VERIFY", "0") == "1"
EVIDENCE_REQUIRE_VERIFIED_APPROVAL = os.getenv("SIMS_EVIDENCE_REQUIRE_VERIFIED_APPROVAL", "1") == "1"
EVIDENCE_EXPIRY_THRESHOLDS = (90, 60, 30, 7, 0)
EVIDENCE_REQUIRED_EXPIRY_TYPES = ()
EVIDENCE_NOTIFICATION_HANDLER = os.getenv("SIMS_EVIDENCE_NOTIFICATION_HANDLER", "")
EVIDENCE_CLASSIFICATIONS = {"PUBLIC": "PUBLIC", "INTERNAL": "INTERNAL", "RESTRICTED": "RESTRICTED", "CONFIDENTIAL": "CONFIDENTIAL", "HIGHLY_RESTRICTED": "HIGHLY_RESTRICTED"}
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["evidence"] = os.getenv("SIMS_EVIDENCE_RATE", "120/min")
