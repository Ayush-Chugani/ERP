from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import VIEWSETS, Metadata, AcceptInvitation, Choices, ClaimInvitation
from .catalogue import PATHS

app_name = "people_master"
router = DefaultRouter()
for model, view in VIEWSETS.items():
    router.register(PATHS[model], view, basename=PATHS[model])
urlpatterns = [
    path("invitations/claim/", ClaimInvitation.as_view()),
    path("choices/<str:resource>/<str:field>/", Choices.as_view()),
    path("metadata/", Metadata.as_view()),
    path("invitations/accept/", AcceptInvitation.as_view()),
    path("", include(router.urls)),
]
