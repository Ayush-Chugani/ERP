from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework.exceptions import APIException


class ProviderUnavailable(APIException):
    status_code = 503
    default_detail = (
        "The required document policy provider is not configured or is unavailable."
    )
    default_code = "document_provider_unavailable"


def invoke(setting, **values):
    path = getattr(settings, setting, "")
    if not path:
        raise ProviderUnavailable()
    try:
        return import_string(path)(**values)
    except ProviderUnavailable:
        raise
    except Exception:  # noqa: BLE001 - redact provider/parser exceptions at the security boundary.
        raise ProviderUnavailable() from None


def policy(institution_id, name, default):
    from django.core.exceptions import ImproperlyConfigured

    settings_map = settings.DOCUMENTS_EXIT_POLICIES
    if not isinstance(settings_map, dict):
        raise ImproperlyConfigured("Document policies must be an object.")
    values = settings_map.get(str(institution_id), {})
    if not isinstance(values, dict):
        raise ImproperlyConfigured("Institution document policy must be an object.")
    value = values.get(name, default)
    if type(value) is not bool:
        raise ImproperlyConfigured("Document policies must be boolean.")
    return value
