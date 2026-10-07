from rest_framework.routers import DefaultRouter

from .api import InternshipViewSet, LookupViewSet

router = DefaultRouter()
router.register("activities", InternshipViewSet, basename="faculty-internship")
router.register("lookups", LookupViewSet, basename="faculty-internship-lookup")
urlpatterns = router.urls
