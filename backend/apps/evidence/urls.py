from rest_framework.routers import DefaultRouter

from .api import DocumentViewSet, LookupViewSet, TagViewSet

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="evidence-document")
router.register("lookups", LookupViewSet, basename="evidence-lookup")
router.register("tags", TagViewSet, basename="evidence-tag")
urlpatterns = router.urls
