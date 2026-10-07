from rest_framework.routers import DefaultRouter

from .api import AwardViewSet, CategoryAdminViewSet, LookupViewSet

router = DefaultRouter()
router.register("activities", AwardViewSet, basename="awards")
router.register("lookups", LookupViewSet, basename="awards-lookup")
router.register(
    "category-admin", CategoryAdminViewSet, basename="awards-category-admin"
)
urlpatterns = router.urls
