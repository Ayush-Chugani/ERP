"""Request correlation only; no personal data is stored in process context."""

from contextvars import ContextVar

request_id = ContextVar("people_request_id", default=None)
