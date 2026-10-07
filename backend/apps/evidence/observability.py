import ipaddress
import logging
from time import perf_counter
from uuid import uuid4

from apps.conferences.api import PrivateResponse

from .audit import denied, request_context

logger = logging.getLogger("sims.evidence")


class ObservedResponse(PrivateResponse):
    def dispatch(self, request, *args, **kwargs):
        identifier = str(uuid4())
        started = perf_counter()
        status = 500
        try:
            ip = str(ipaddress.ip_address(request.META.get("REMOTE_ADDR", "")))
        except ValueError:
            ip = None
        token = request_context.set(
            {
                "id": identifier,
                "ip": ip,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            }
        )
        try:
            response = super().dispatch(request, *args, **kwargs)
            status = response.status_code
            response["X-Request-ID"] = identifier
            # Denials before entering domain services (e.g. scoped detail lookup) also have an audit.
            if status in (403, 404) and kwargs.get("pk") and request.method == "GET":
                denied(getattr(self.request, "user", None), kwargs["pk"])
            return response
        finally:
            actor = getattr(getattr(self, "request", None), "user", None)
            logger.log(
                logging.ERROR if status >= 500 else logging.INFO,
                "m33_request",
                extra={
                    "request_identifier": identifier,
                    "actor_id": getattr(actor, "pk", None),
                    "record_id": kwargs.get("pk"),
                    "operation": getattr(self, "action", request.method),
                    "status_code": status,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            request_context.reset(token)
