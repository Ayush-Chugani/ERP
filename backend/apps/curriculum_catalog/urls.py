from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import VIEWSETS, Metadata, Choices
from .policies import PATHS

app_name = "curriculum_catalog"
router = DefaultRouter()
for model, viewset in VIEWSETS.items():
    router.register(PATHS[model], viewset, basename=PATHS[model])
urlpatterns = [
    path("metadata/", Metadata.as_view()),
    path("choices/<str:kind>/", Choices.as_view()),
    path("", include(router.urls)),
]
