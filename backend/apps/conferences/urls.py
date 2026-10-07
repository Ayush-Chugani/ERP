from rest_framework.routers import DefaultRouter

from .api import ActivityViewSet, EventViewSet, LookupViewSet

router = DefaultRouter()
router.register("events", EventViewSet, basename="conference-event")
router.register("activities", ActivityViewSet, basename="conference-activity")
router.register("lookups", LookupViewSet, basename="conference-lookup")
urlpatterns = router.urls
