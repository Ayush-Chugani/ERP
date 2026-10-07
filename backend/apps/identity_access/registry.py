"""Scope adapters are registered by server-side business code, never by clients."""
from .evaluator import Scope, has_object_permission

_adapters = {}


def register(model, adapter):
    if model in _adapters and _adapters[model] is not adapter:
        raise ValueError('Scope adapter already registered.')
    _adapters[model] = adapter


def allowed(user, code, obj):
    adapter = _adapters.get(type(obj))
    if adapter is None:
        return False
    scopes = tuple(adapter(obj))
    return bool(scopes) and all(isinstance(s, Scope) for s in scopes) and has_object_permission(user, code, scopes=scopes)


def filter_authorized(user, code, queryset, *, scope_filter):
    """The owner supplies a SQL Q filter; never filter after pagination/object lookup.

    Owners must include effective DENY exclusions in their tested scope_filter.
    An absent filter yields no records instead of falling back to unrestricted data.
    """
    if not callable(scope_filter):
        return queryset.none()
    predicate = scope_filter(user, code)
    return queryset.none() if predicate is None else queryset.filter(predicate)
