"""FastAPI application factory."""
import logging
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

import app.models  # noqa: F401  (register every table)
from app.api.routers import (
    admissions,
    ai,
    assessments,
    attendance,
    auth,
    communication,
    feedback,
    files,
    health,
    hr_secure,
    meta,
    security,
    timetable,
    workspace,
)
from app.config import get_settings
from app.core.errors import install_handlers
from app.core.middleware import SecurityMiddleware
from app.resources.router import resource_routers

API_PREFIX = "/api/v1"

CONVENTIONS = """

**Conventions** — all endpoints live under `/api/v1`.

* **Auth**: `POST /auth/login` returns a short-lived bearer `access` token (send `Authorization: Bearer …`) and sets a
  rotating HttpOnly refresh cookie used by `POST /auth/refresh`.
* **Errors** are always `{"error": {"code", "message", "details"}}`; on validation errors `details` maps field names to messages.
* **Lists** return `{count, page, page_size, next, previous, results}`; filter with `?field=`, `?field__in=a,b`,
  `?field__gte=`; search with `?search=`; sort with `?ordering=-field`; page with `?page=&page_size=` (max 100).
* **Creates** may send an `Idempotency-Key` header; **updates** send the record's `version` (or `If-Match`) to detect conflicts.
* **Workflow** buttons are `POST …/{id}/actions/{name}` with an optional `{"remarks": "…"}` body.
"""


class ErrorBody(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["Some values are invalid."])
    details: dict[str, Any] | list[Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in, or the session expired."},
    403: {"model": ErrorResponse, "description": "Signed in but not allowed to do this."},
    404: {"model": ErrorResponse, "description": "Not found, or outside your access scope."},
    409: {"model": ErrorResponse, "description": "Conflicts with the record's current state or with unique data."},
    422: {"model": ErrorResponse, "description": "Validation failed; see `error.details`."},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
}


def _operation_id(route: APIRoute) -> str:
    tag = (route.tags[0] if route.tags else "api")
    tag = "".join(c if c.isalnum() else "_" for c in str(tag).lower())
    return f"{tag}__{route.name}"


def _openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=(app.description or "") + CONVENTIONS,
                         routes=app.routes)
    comps = schema.setdefault("components", {})
    for name in ("HTTPValidationError", "ValidationError"):   # replaced by our envelope everywhere
        comps.get("schemas", {}).pop(name, None)
    for path in schema["paths"].values():
        for op in path.values():
            r422 = op.get("responses", {}).get("422")
            if r422:
                r422["content"] = {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}
    comps.setdefault("securitySchemes", {})["HTTPBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    app.openapi_schema = schema
    return schema


def create_app() -> FastAPI:
    s = get_settings()
    logging.basicConfig(level=logging.INFO if s.env != "test" else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(
        title="SIMS API", version="1.0.0", description="Student Information Management System.",
        docs_url="/api/docs" if s.docs_enabled else None, redoc_url=None,
        openapi_url="/api/openapi.json" if s.docs_enabled else None,
        generate_unique_id_function=_operation_id,
    )
    app.openapi = lambda: _openapi(app)  # type: ignore[method-assign]
    install_handlers(app)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                           allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
                           allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key",
                                          "If-Match", "X-Request-ID"], max_age=600)
    app.add_middleware(SecurityMiddleware)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health.router)
    for r in (auth.router, meta.router, security.router, workspace.router, admissions.router, attendance.router,
              assessments.router, timetable.router, feedback.router, communication.router, ai.router, files.router,
              hr_secure.router):
        api.include_router(r, responses=ERRORS)
    for r in resource_routers():
        api.include_router(r, responses=ERRORS)
    app.include_router(api)
    return app


app = create_app()
