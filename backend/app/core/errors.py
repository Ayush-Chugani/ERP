"""One error envelope for every failure: {"error": {"code", "message", "details"}}."""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("sims.errors")


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.details = details if details is not None else {}


class NotFound(AppError):
    status, code = 404, "not_found"

    def __init__(self, message: str = "Not found."):
        super().__init__(message)


class Forbidden(AppError):
    status, code = 403, "permission_denied"

    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message)


class Unauthorized(AppError):
    status, code = 401, "not_authenticated"

    def __init__(self, message: str = "Authentication required."):
        super().__init__(message)


class Conflict(AppError):
    status, code = 409, "conflict"


class Throttled(AppError):
    status, code = 429, "throttled"


class Invalid(AppError):
    status, code = 422, "validation_error"


def envelope(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details if details is not None else {}}}


def _json(status: int, code: str, message: str, details: Any = None, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(envelope(code, message, details), status_code=status, headers=headers)


def _friendly_integrity(exc: IntegrityError) -> tuple[int, str, str]:
    diag = getattr(exc.orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None) or ""
    sqlstate = getattr(exc.orig, "sqlstate", "") or ""
    if sqlstate == "23505":
        return 409, "duplicate", "A record with the same unique values already exists."
    if sqlstate == "23503":
        return 409, "in_use", "The record is referenced by other data, or points to a record that does not exist."
    if sqlstate == "23502":
        col = getattr(diag, "column_name", "") or "a required field"
        return 422, "validation_error", f"{col} is required."
    if sqlstate == "23514":
        msg = f"The values violate rule {constraint}." if constraint else "The values violate a data rule."
        return 422, "validation_error", msg
    return 409, "integrity_error", "The change conflicts with existing data."


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _json(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {401: "not_authenticated", 403: "permission_denied", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error")
        msg = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404 and msg == "Not Found":
            msg = "Not found."
        return _json(exc.status_code, code, msg, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
            details.setdefault(".".join(loc) or "non_field_errors", []).append(err["msg"])
        return _json(422, "validation_error", "Some values are invalid.", details)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        status, code, message = _friendly_integrity(exc)
        log.info("integrity error: %s", exc.orig)
        return _json(status, code, message)

    @app.exception_handler(DBAPIError)
    async def _dbapi(_: Request, exc: DBAPIError):
        sqlstate = getattr(exc.orig, "sqlstate", "") or ""
        if sqlstate == "23001":  # restrict_violation raised by the append-only triggers
            return _json(409, "append_only", "This record is append-only and cannot be changed.")
        if sqlstate.startswith("22"):  # data exception: a value outside what the column can hold
            log.info("data exception: %s", sqlstate)
            return _json(422, "invalid_value", "A value is out of the allowed range or format.")
        log.exception("database error")
        return _json(503 if exc.connection_invalidated else 500, "server_error", "A database error occurred.")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return _json(500, "server_error", "An unexpected error occurred.")
