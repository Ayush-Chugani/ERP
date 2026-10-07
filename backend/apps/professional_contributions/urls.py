from rest_framework.routers import DefaultRouter

from .api import ContributionViewSet, LookupViewSet, TypeAdminViewSet

router = DefaultRouter()
router.register(
    "activities", ContributionViewSet, basename="professional_contributions"
)
router.register("lookups", LookupViewSet, basename="professional_contributions-lookup")
router.register(
    "type-admin", TypeAdminViewSet, basename="professional_contributions-type-admin"
)
urlpatterns = router.urls
