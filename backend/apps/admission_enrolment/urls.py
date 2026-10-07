from rest_framework.routers import SimpleRouter
from .api import Applicants, Applications, Enrolments, History

router=SimpleRouter()
router.register('applicants',Applicants,basename='admission-applicant')
router.register('applications',Applications,basename='admission-application')
router.register('enrolments',Enrolments,basename='admission-enrolment')
router.register('history',History,basename='admission-history')
urlpatterns=router.urls
