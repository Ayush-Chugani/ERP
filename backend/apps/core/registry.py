from dataclasses import dataclass
from django.core.exceptions import ImproperlyConfigured

@dataclass(frozen=True)
class Module:
    code: str
    app: str
    dependencies: tuple[str, ...]
    namespace: str
    api_prefix: str
    navigation: tuple[tuple[str, str, int], ...]
    permissions: tuple[str, ...]

MODULES = (
    Module("COMMUNICATION","apps.communication",("DOCUMENTS_EXIT","PEOPLE_MASTER","ORGANIZATION","ADMISSION_ENROLMENT","ACCOUNTS","CORE"),"communication","/api/v1/communication/",(("Communication","/communication",1400),),()),
    Module('DOCUMENTS_EXIT','apps.documents_exit',('PEOPLE_MASTER','COMMON_REFERENCE','ADMISSION_ENROLMENT','ACCOUNTS','CORE'),'documents_exit','/api/v1/documents/',(('Documents and exits','/documents',1300),),()),
    Module('STUDENT_SUPPORT','apps.student_support',('PEOPLE_MASTER','ORGANIZATION','ACCOUNTS','CORE'),'student_support','/api/v1/support/',(('Student support','/support',1200),),()),
    Module('FEEDBACK','apps.feedback',('TERM_REGISTRATION','TEACHING_TIMETABLE','ACADEMIC_CALENDAR'),'feedback','/api/v1/feedback/',(('Feedback','/feedback',1100),),()),
    Module('ASSESSMENTS_RESULTS', 'apps.assessments_results', ('TERM_REGISTRATION','TEACHING_TIMETABLE','CURRICULUM_CATALOG'), 'assessments_results', '/api/v1/assessments/', (('Assessment and results','/assessments',1000),), ()),
    Module('ATTENDANCE_LESSON_PLAN', 'apps.attendance_lesson_plan', ('TEACHING_TIMETABLE','TERM_REGISTRATION','PEOPLE_MASTER','ACADEMIC_CALENDAR'), 'attendance_lesson_plan', '/api/v1/attendance/', (('Attendance and lesson plans','/attendance',900),), ()),
    Module('TEACHING_TIMETABLE', 'apps.teaching_timetable', ('TERM_REGISTRATION', 'PEOPLE_MASTER', 'ACADEMIC_CALENDAR', 'ORGANIZATION'),
        'teaching_timetable', '/api/v1/timetable/', (('Teaching and timetable', '/timetable', 800),), ()),
    Module('TERM_REGISTRATION', 'apps.term_registration', ('ORGANIZATION','ACADEMIC_CALENDAR','CURRICULUM_CATALOG','PEOPLE_MASTER','ADMISSION_ENROLMENT'),
        'term_registration', '/api/v1/registration/', (('Term registration', '/registration', 700),), ()),
    Module('ADMISSION_ENROLMENT', 'apps.admission_enrolment', ('ACCOUNTS','ORGANIZATION','ACADEMIC_CALENDAR','CURRICULUM_CATALOG','PEOPLE_MASTER'),
        'admission_enrolment', '/api/v1/admissions/', (), ()),
    Module("PEOPLE_MASTER", "apps.people_master", ("CORE", "ACCOUNTS", "COMMON_REFERENCE", "ORGANIZATION", "CURRICULUM_CATALOG"),
        "people_master", "/api/v1/people/", (), ()),
    Module("CURRICULUM_CATALOG", "apps.curriculum_catalog", ("CORE", "ACCOUNTS", "ORGANIZATION", "ACADEMIC_CALENDAR"),
        "curriculum_catalog", "/api/v1/curriculum/", (("Curriculum catalog", "/curriculum", 400),), ()),
    Module("ACADEMIC_CALENDAR", "apps.academic_calendar", ("CORE", "ACCOUNTS", "ORGANIZATION"),
        "academic_calendar", "/api/v1/calendar/", (("Academic calendar", "/calendar", 300),), ()),
    Module("ORGANIZATION", "apps.organization", ("CORE", "ACCOUNTS", "COMMON_REFERENCE"),
        "organization", "/api/v1/organization/", (("Organization structure", "/organization", 200),), ()),
    Module("CORE", "apps.core", (), "core", "/api/v1/core/", (), ()),
    Module("ACCOUNTS", "apps.accounts", ("CORE",), "accounts", "/api/v1/auth/", (),
        ("accounts.manage_platform_access",)),
    Module("COMMON_REFERENCE", "apps.common_reference", ("CORE", "ACCOUNTS"),
        "common_reference", "/api/v1/reference/", (("Reference data", "/reference", 100),),
        ("common_reference.view_reference", "common_reference.maintain_reference")),
)

def validate_registry(modules=MODULES):
    for attr in ("code", "namespace", "api_prefix", "app"):
        values = [getattr(m, attr) for m in modules]
        if len(set(values)) != len(values):
            raise ImproperlyConfigured(f"Duplicate module {attr}")
    from django.apps import apps
    installed = {app.name for app in apps.get_app_configs()}
    by_code = {m.code: m for m in modules}
    done, visiting = set(), set()
    def visit(code):
        if code not in by_code or code in visiting:
            raise ImproperlyConfigured("Unknown or cyclic module dependency")
        if code in done:
            return
        visiting.add(code)
        for dependency in by_code[code].dependencies:
            visit(dependency)
        visiting.remove(code)
        done.add(code)
    for module in modules:
        if module.app not in installed:
            raise ImproperlyConfigured("Registry app is not installed")
        visit(module.code)
