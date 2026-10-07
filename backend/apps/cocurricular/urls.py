from rest_framework.routers import DefaultRouter

from .api import CategoryAdminViewSet, CocurricularViewSet, LookupViewSet

router = DefaultRouter()
router.register("activities", CocurricularViewSet, basename="cocurricular")
router.register("lookups", LookupViewSet, basename="cocurricular-lookup")
router.register(
    "category-admin", CategoryAdminViewSet, basename="cocurricular-category-admin"
)
urlpatterns = router.urls
