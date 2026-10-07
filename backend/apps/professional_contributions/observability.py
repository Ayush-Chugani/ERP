"""Private request diagnostics through the platform's Python logging pipeline."""

import logging
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from apps.conferences.api import PrivateResponse
from apps.identity_access.audit import record as audit_record

request_identifier = ContextVar("m32_request_identifier", default=None)
logger = logging.getLogger("sims.professional_contributions")


def record(**kwargs):
    kwargs.setdefault("request_id", request_identifier.get())
    return audit_record(**kwargs)


class ObservedResponse(PrivateResponse):
    def dispatch(self, request, *args, **kwargs):
        identifier = str(uuid4())
        token = request_identifier.set(identifier)
        started = perf_counter()
        status = 500
        try:
            response = super().dispatch(request, *args, **kwargs)
            status = response.status_code
            response["X-Request-ID"] = identifier
            return response
        finally:
            actor = getattr(getattr(self, "request", None), "user", None)
            logger.log(
                logging.ERROR if status >= 500 else logging.INFO,
                "m32_request",
                extra={
                    "request_identifier": identifier,
                    "actor_id": getattr(actor, "pk", None),
                    "record_id": kwargs.get("pk"),
                    "operation": getattr(self, "action", request.method),
                    "status_code": status,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            request_identifier.reset(token)
