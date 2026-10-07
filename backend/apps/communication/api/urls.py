from django.urls import path

from .. import services as s
from . import serializers as z
from . import views as v

app_name = "communication"
urlpatterns = [
    path("drafts/create/", v.mutation(z.Write, s.write)),
    path("drafts/<int:pk>/edit/", v.mutation(z.Write, s.write)),
    path("types/create/", v.mutation(z.TypeWrite, s.write_type)),
    path("types/<int:pk>/edit/", v.mutation(z.TypeWrite, s.write_type)),
    path("drafts/<int:pk>/upload/", v.mutation(z.Upload, s.upload_attachment)),
    path("audit/<int:pk>/", v.Audit.as_view()),
    path("lookups/<str:resource>/", v.Lookups.as_view()),
    path(
        "<str:workspace>/<int:pk>/attachments/<int:file_id>/download/",
        v.Download.as_view(),
    ),
    path("<str:workspace>/<int:pk>/", v.Detail.as_view()),
    path("<str:workspace>/", v.Records.as_view()),
]
for action in ["submit", "approve", "reject", "revise", "archive"]:
    urlpatterns.insert(
        0,
        path(
            "drafts/<int:pk>/" + action + "/",
            v.mutation(z.Workflow, s.workflow, action=action),
        ),
    )
for action in ["attach", "detach", "reorder"]:
    urlpatterns.insert(
        0,
        path(
            "drafts/<int:pk>/" + action + "/",
            v.mutation(z.Attachment, s.attachment, action=action),
        ),
    )
