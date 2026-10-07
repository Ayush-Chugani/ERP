from rest_framework.routers import DefaultRouter

from .api import LookupViewSet, ProjectViewSet

router = DefaultRouter()
router.register("activities", ProjectViewSet, basename="funded-project")
router.register("lookups", LookupViewSet, basename="funded-project-lookup")
urlpatterns = router.urls
