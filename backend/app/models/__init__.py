"""Import every model module so Base.metadata is complete."""
from app.models import academic_calendar  # noqa: F401
from app.models import accounts  # noqa: F401
from app.models import admission_enrolment  # noqa: F401
from app.models import assessments_results  # noqa: F401
from app.models import attendance_lesson_plan  # noqa: F401
from app.models import awards  # noqa: F401
from app.models import cocurricular  # noqa: F401
from app.models import common_reference  # noqa: F401
from app.models import communication  # noqa: F401
from app.models import conferences  # noqa: F401
from app.models import consultancy  # noqa: F401
from app.models import curriculum_catalog  # noqa: F401
from app.models import documents_exit  # noqa: F401
from app.models import employee_hr  # noqa: F401
from app.models import evidence  # noqa: F401
from app.models import extracurricular  # noqa: F401
from app.models import faculty_internships  # noqa: F401
from app.models import feedback  # noqa: F401
from app.models import funded_projects  # noqa: F401
from app.models import identity_access  # noqa: F401
from app.models import organization  # noqa: F401
from app.models import people_master  # noqa: F401
from app.models import professional_contributions  # noqa: F401
from app.models import professional_memberships  # noqa: F401
from app.models import research_proposals  # noqa: F401
from app.models import research_publications  # noqa: F401
from app.models import staff_activities  # noqa: F401
from app.models import staff_profile  # noqa: F401
from app.models import student_support  # noqa: F401
from app.models import teaching_timetable  # noqa: F401
from app.models import tenancy  # noqa: F401
from app.models import term_registration  # noqa: F401
from app.models import platform  # noqa: F401
from app.models import extras  # noqa: F401

from app.db.base import Base  # noqa: E402
from app.db.naming import normalise  # noqa: E402

normalise(Base.metadata)
