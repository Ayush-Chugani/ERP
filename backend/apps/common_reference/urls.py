from rest_framework.routers import SimpleRouter
from .views import VIEWSETS
app_name="common_reference"
router=SimpleRouter()
for path,viewset in VIEWSETS.items(): router.register(path,viewset,basename=path)
urlpatterns=router.urls
