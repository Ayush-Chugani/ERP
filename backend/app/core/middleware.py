"""Security headers, request ids, body-size limit and trusted-host enforcement as pure ASGI middleware."""
import json
import logging
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.core.errors import envelope

log = logging.getLogger("sims.access")

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-site",
    "permissions-policy": "geolocation=(), microphone=(), camera=()",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}
DOC_PREFIXES = ("/api/docs", "/api/redoc")


class _TooLarge(Exception):
    pass


class SecurityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        s = get_settings()
        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        if len(request_id) > 64 or not request_id.replace("-", "").isalnum():
            request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        host = headers.get("host", "").split(":")[0].lower()
        if s.allowed_hosts and "*" not in s.allowed_hosts and host not in {h.lower() for h in s.allowed_hosts}:
            return await self._reject(send, 400, "invalid_host", "Invalid host header.", request_id)

        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > s.max_body_bytes:
            return await self._reject(send, 413, "payload_too_large", "Request body is too large.", request_id)

        received = 0
        overflow = {"hit": False, "replied": False}

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > s.max_body_bytes:
                    overflow["hit"] = True
                    raise _TooLarge()
            return message

        started = time.perf_counter()
        status_holder = {"code": 0}
        path = scope["path"]

        async def send_wrapper(message: Message):
            if overflow["hit"] and message["type"] in ("http.response.start", "http.response.body"):
                # a framework layer may have turned the abort into a 400; the client must still see 413
                if not overflow["replied"]:
                    overflow["replied"] = True
                    status_holder["code"] = 413
                    await self._reject(send, 413, "payload_too_large", "Request body is too large.", request_id)
                return
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                h = MutableHeaders(scope=message)
                for k, v in SECURITY_HEADERS.items():
                    if k == "content-security-policy" and path.startswith(DOC_PREFIXES):
                        continue
                    h.setdefault(k, v)
                h["x-request-id"] = request_id
                if path.startswith("/api/"):
                    h.setdefault("cache-control", "no-store")
                if s.env == "production":
                    h.setdefault("strict-transport-security", "max-age=31536000; includeSubDomains")
            await send(message)

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except _TooLarge:  # pragma: no cover - normally converted by send_wrapper first
            await send_wrapper({"type": "http.response.start", "status": 413, "headers": []})
        finally:
            log.info("%s %s -> %s %.1fms rid=%s", scope["method"], path, status_holder["code"],
                     (time.perf_counter() - started) * 1000, request_id)

    @staticmethod
    async def _reject(send, status: int, code: str, message: str, request_id: str):
        body = json.dumps(envelope(code, message)).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
            (b"x-request-id", request_id.encode()), (b"x-content-type-options", b"nosniff")]})
        await send({"type": "http.response.body", "body": body})
