from rest_framework.routers import DefaultRouter

from .api import LookupViewSet, ProposalViewSet

router = DefaultRouter()
router.register("activities", ProposalViewSet, basename="research-proposal")
router.register("lookups", LookupViewSet, basename="research-proposal-lookup")
urlpatterns = router.urls
