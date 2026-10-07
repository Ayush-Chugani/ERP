from django.contrib import admin
from django.urls import path, include, re_path
from apps.core.errors import not_found
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.views import ApiRoot, Liveness, Readiness
urlpatterns = [
    path("api/v1/evidence/", include("apps.evidence.urls")),
    path("api/v1/professional-contributions/", include("apps.professional_contributions.urls")),
    path('api/v1/professional-memberships/', include('apps.professional_memberships.urls')),
    path('api/v1/awards/', include('apps.awards.urls')),
    path('api/v1/extracurricular/', include('apps.extracurricular.urls')),
    path('api/v1/cocurricular/', include('apps.cocurricular.urls')),
    path('api/v1/employee-hr/', include('apps.employee_hr.api.urls')),
    path('api/v1/security/', include('apps.identity_access.api')),
    path("api/v1/communication/", include("apps.communication.api.urls")),
    path('api/v1/documents/', include('apps.documents_exit.api.urls')),
    path('api/v1/support/', include('apps.student_support.api.urls')),
    path('api/v1/feedback/', include('apps.feedback.api.urls')),
    path('api/v1/assessments/', include('apps.assessments_results.api.urls')),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", ApiRoot.as_view(), name="api-root"),
    path("api/v1/core/live/", Liveness.as_view(), name="live"),
    path("api/v1/core/ready/", Readiness.as_view(), name="ready"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/reference/", include("apps.common_reference.urls")),
    path("api/v1/organization/", include("apps.organization.urls")),
    path("api/v1/calendar/", include("apps.academic_calendar.urls")),
    path("api/v1/curriculum/", include("apps.curriculum_catalog.urls")),
    path("api/v1/people/", include("apps.people_master.urls")),
    path("api/v1/admissions/", include("apps.admission_enrolment.urls")),
    path("api/v1/attendance/", include("apps.attendance_lesson_plan.urls")),
    path("api/v1/registration/", include("apps.term_registration.urls")),
    path("api/v1/timetable/", include("apps.teaching_timetable.urls")),
    path('api/v1/consultancy/', include('apps.consultancy.urls')),
    path('api/v1/funded-projects/', include('apps.funded_projects.urls')),
    path('api/v1/research-proposals/', include('apps.research_proposals.urls')),
    path('api/v1/faculty-internships/', include('apps.faculty_internships.urls')),
    path('api/v1/conferences/', include('apps.conferences.urls')),
    re_path(r"^api/.*$", not_found),
]
handler404 = "apps.core.errors.not_found"
handler500 = "apps.core.errors.server_error"

