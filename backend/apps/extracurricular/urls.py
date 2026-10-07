from rest_framework.routers import DefaultRouter

from .api import CategoryAdminViewSet, ExtracurricularViewSet, LookupViewSet

router = DefaultRouter()
router.register("activities", ExtracurricularViewSet, basename="extracurricular")
router.register("lookups", LookupViewSet, basename="extracurricular-lookup")
router.register(
    "category-admin", CategoryAdminViewSet, basename="extracurricular-category-admin"
)
urlpatterns = router.urls
