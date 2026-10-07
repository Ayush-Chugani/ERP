from rest_framework.routers import SimpleRouter
from .views import VIEWSETS
from django.urls import path
from .metadata import OrganizationMetadata
app_name='organization'
router=SimpleRouter()
for resource_path,view in VIEWSETS.items():router.register(resource_path,view,basename=resource_path)
urlpatterns=[path('metadata/',OrganizationMetadata.as_view())]+router.urls
