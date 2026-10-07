from django.urls import path

from .. import services as s
from . import serializers as z
from . import views as v

app_name = "student_support"
urlpatterns = [
    path("assignments/create/", v.mutation(z.MentorCreate, s.assign_mentor)),
    path("assignments/<int:pk>/end/", v.mutation(z.MentorEnd, s.end_assignment)),
    path(
        "assignments/<int:pk>/cancel/",
        v.mutation(z.MentorEnd, s.end_assignment, cancel=True),
    ),
    path("assignments/<int:pk>/change/", v.mutation(z.MentorChange, s.change_mentor)),
    path("sessions/schedule/", v.mutation(z.SessionSchedule, s.schedule_session)),
    path("own-grievances/submit/", v.mutation(z.GrievanceSubmit, s.submit_grievance)),
    path("categories/create/", v.mutation(z.CategoryWrite, s.category_write)),
    path("categories/<int:pk>/edit/", v.mutation(z.CategoryWrite, s.category_write)),
    path("grievances/<int:pk>/history/", v.History.as_view()),
    path("reports/", v.Report.as_view()),
]
for action, serializer in [
    ("complete", z.SessionComplete),
    ("follow-up", z.SessionFollowUp),
    ("cancel", z.SessionCancel),
    ("reschedule", z.SessionReschedule),
    ("confidentiality", z.SessionConfidentiality),
]:
    urlpatterns.append(
        path(
            "sessions/<int:pk>/" + action + "/",
            v.mutation(serializer, s.session_action, action=action),
        )
    )
for action, serializer in [
    ("assign", z.GrievanceAssign),
    ("review", z.GrievanceReview),
    ("resolve", z.GrievanceResolve),
    ("reject", z.GrievanceReject),
    ("close", z.GrievanceClose),
]:
    urlpatterns.append(
        path(
            "grievances/<int:pk>/" + action + "/",
            v.mutation(serializer, s.grievance_action, action=action),
        )
    )
urlpatterns += [
    path("<str:resource>/", v.Records.as_view()),
    path("<str:resource>/<int:pk>/", v.Detail.as_view()),
]
