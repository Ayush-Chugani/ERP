"""A small allowlisted audit envelope; secrets are rejected at the boundary."""
import re
from .models import ActivityAudit

FORBIDDEN = re.compile(r'password|secret|token|cookie|authorization|credential|recovery|otp|seed|hash', re.I)


def safe(value):
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if FORBIDDEN.search(str(k)) else safe(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    return str(value)


def record(*, actor, action, entity=None, before=None, after=None, details=None,
           module='IAM', request_id=None, ip=None):
    return ActivityAudit.objects.create(user=actor, module_code=module, action_code=action,
        entity_name=entity._meta.db_table if entity is not None else None,
        entity_id=str(entity.pk) if entity is not None else None,
        request_identifier=request_id, ip_address=ip,
        before_values=safe(before), after_values=safe(after), details=safe(details))
