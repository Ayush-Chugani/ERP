from django.core.checks import Error,register
from django.conf import settings

@register()
def activation_consistency(app_configs,**kwargs):
    if settings.IDENTITY_ACCESS_ENABLED and not settings.IDENTITY_ACCESS_SECURITY_ENABLED:
        return [Error('Enable M15 account security before enabling its administration APIs.',id='identity_access.E001')]
    return []
