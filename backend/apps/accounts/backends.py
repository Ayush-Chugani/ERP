from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

class SecurityModelBackend(ModelBackend):
    def user_can_authenticate(self,user):
        if not super().user_can_authenticate(user): return False
        if not settings.IDENTITY_ACCESS_SECURITY_ENABLED: return True
        from apps.identity_access.evaluator import usable
        # Django admin/session login has no step-up ceremony. Fail closed there.
        return usable(user,timezone.now()) and not user.must_change_password and not user.multi_factor_enabled
