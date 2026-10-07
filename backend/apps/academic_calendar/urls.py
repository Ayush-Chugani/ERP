from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import VIEWSETS, Metadata, ParentChoices
from .services import PATHS

app_name = 'academic_calendar'
router = DefaultRouter()
for model, viewset in VIEWSETS.items():
    router.register(PATHS[model], viewset, basename=PATHS[model])
urlpatterns = [path('metadata/', Metadata.as_view()), path('campus-choices/', ParentChoices.as_view()), path('', include(router.urls))]
