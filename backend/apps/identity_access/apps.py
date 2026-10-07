from django.apps import AppConfig

class IdentityAccessConfig(AppConfig):
    name='apps.identity_access'
    def ready(self):
        from . import checks
