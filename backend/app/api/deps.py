"""Shared request dependencies: client address, authenticated principal, permission guards."""
import time
from collections.abc import Callable
from threading import Lock

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import Forbidden, Unauthorized
from app.core.ratelimit import local_limiter
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.accounts import UserAccount
from app.models.platform import AuthSession
from app.rbac.engine import Principal, load_principal

bearer = HTTPBearer(auto_error=False, description="Access token from POST /api/v1/auth/login")
PRINCIPAL_TTL = 10.0
_cache: dict[tuple[int, str, int], tuple[float, Principal]] = {}
_cache_lock = Lock()


def client_ip(request: Request) -> str:
    s = get_settings()
    peer = request.client.host if request.client else "unknown"
    hops = s.trusted_proxy_hops
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops][:45]
    return peer[:45]


def forget_principals(user_id: int | None = None) -> None:
    with _cache_lock:
        for k in [k for k in _cache if user_id is None or k[0] == user_id]:
            del _cache[k]


def current_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Principal:
    cached = getattr(request.state, "principal", None)
    if cached is not None:  # pragma: no cover - only when a route lists the dependency twice
        return cached
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized()
    try:
        claims = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise Unauthorized("Your session has expired. Sign in again.") from None
    user_id, sid = int(claims["sub"]), claims["sid"]
    row = db.execute(
        select(UserAccount, AuthSession)
        .join(AuthSession, AuthSession.user_id == UserAccount.user_id)
        .where(UserAccount.user_id == user_id, AuthSession.session_id == sid)
    ).first()
    if row is None:
        raise Unauthorized("Your session has expired. Sign in again.")
    user, sess = row
    from datetime import UTC, datetime

    if (sess.revoked_at is not None or sess.expires_at <= datetime.now(UTC) or not user.is_active
            or user.account_status != "ACTIVE" or user.security_version != claims.get("sv")):
        raise Unauthorized("Your session has expired. Sign in again.")
    key = (user_id, sid, user.security_version)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < PRINCIPAL_TTL:
            principal = hit[1]
        else:
            principal = None
    if principal is None:
        principal = load_principal(db, user, sid)
        with _cache_lock:
            if len(_cache) > 5000:  # pragma: no cover - memory guard
                _cache.clear()
            _cache[key] = (now, principal)
    request.state.principal = principal
    s = get_settings()
    local_limiter.hit(f"u:{user_id}", s.rate_default)
    return principal


def active_principal(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    """Principal that is allowed to use the application (not forced to rotate a temporary password first)."""
    if principal.must_change_password:
        raise Forbidden("You must change your password before continuing.")
    return principal


def require(module: str, resource: str, action: str) -> Callable[..., Principal]:
    """Dependency enforcing that the caller holds ``MODULE.RESOURCE.ACTION`` (or ``MODULE.ALL.ACTION``) at any scope.
    Row-level scoping is applied separately by the resource layer."""

    def dep(principal: Principal = Depends(active_principal)) -> Principal:
        if not principal.can(module, resource, action):
            raise Forbidden()
        return principal

    return dep
