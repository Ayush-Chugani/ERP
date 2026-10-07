from rest_framework.routers import DefaultRouter

from .api import LookupViewSet, MembershipViewSet, TypeAdminViewSet

router = DefaultRouter()
router.register("", MembershipViewSet, basename="professional_memberships")
router.register("lookups", LookupViewSet, basename="professional_memberships-lookup")
router.register(
    "type-admin", TypeAdminViewSet, basename="professional_memberships-type-admin"
)
urlpatterns = router.urls
