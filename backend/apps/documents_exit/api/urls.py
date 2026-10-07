from django.urls import path

from .. import services as s
from . import serializers as z
from . import views as v

app_name = "documents_exit"
urlpatterns = [
    path("<str:resource>/<int:pk>/audit/", v.Audit.as_view()),
    path("documents/upload/", v.mutation(z.Upload, s.upload_document)),
    path("documents/<int:pk>/replace/", v.mutation(z.Update, s.update_document)),
    path("documents/<int:pk>/verify/", v.mutation(z.Verify, s.verify_document)),
    path(
        "documents/<int:pk>/delete-file/",
        v.mutation(z.Delete, s.access_file, resource="documents", delete=True),
    ),
    path("types/create/", v.mutation(z.TypeWrite, s.certificate_type)),
    path("types/<int:pk>/edit/", v.mutation(z.TypeWrite, s.certificate_type)),
    path(
        "certificates/submit/", v.mutation(z.RequestCertificate, s.request_certificate)
    ),
    path("certificates/<int:pk>/issue/", v.mutation(z.Issue, s.issue_certificate)),
    path("exits/finalize/", v.mutation(z.Exit, s.finalize_exit)),
]
for action in ["review", "approve", "reject", "cancel"]:
    urlpatterns.append(
        path(
            "certificates/<int:pk>/" + action + "/",
            v.mutation(z.CertificateAction, s.certificate_action, action=action),
        )
    )
urlpatterns += [
    path("<str:resource>/<int:pk>/download/", v.Download.as_view()),
    path("<str:resource>/<int:pk>/", v.Detail.as_view()),
    path("<str:resource>/", v.Records.as_view()),
]
