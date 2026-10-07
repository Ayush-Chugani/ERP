from rest_framework.routers import DefaultRouter

from .api import ConsultancyLookupViewSet, ConsultancyViewSet

router = DefaultRouter()
router.register("activities", ConsultancyViewSet, basename="consultancy")
router.register("lookups", ConsultancyLookupViewSet, basename="consultancy-lookup")
urlpatterns = router.urls
