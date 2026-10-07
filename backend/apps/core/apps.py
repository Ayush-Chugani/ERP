from django.apps import AppConfig
class CoreConfig(AppConfig):
    name = "apps.core"
    def ready(self):
        from .registry import validate_registry
        validate_registry()
