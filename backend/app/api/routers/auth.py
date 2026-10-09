"""Authentication API: CSRF bootstrap, login, refresh rotation, logout, profile, password and MFA management."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import client_ip, current_principal, forget_principals
from app.config import get_settings
from app.core import totp
from app.core.errors import Forbidden, Invalid, NotFound, Unauthorized
from app.core.ratelimit import db_hit
from app.core.security import create_access_token, csrf_token_for, verify_csrf, verify_password
from app.db.session import get_db
from app.models.accounts import UserAccount
from app.models.platform import AuthSession
from app.rbac.engine import Principal
from app.rbac.portals import PORTALS, portals_of
from app.services import auth as svc
from app.services.auth import audit_login

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "sims_refresh"
CSRF_COOKIE = "sims_csrf"
AUTH_PATH = "/api/v1/auth"


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=256)
    mfa: str | None = Field(default=None, max_length=12)
    portal: Literal["student", "faculty", "leadership", "office", "exam", "support", "organisation", "admin"] | None = Field(
        default=None, description="Entrance used to sign in; the account must belong to it. Omit for API clients.")


class PasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class MfaCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(max_length=12)
    password: str | None = Field(default=None, max_length=256)


def _set_csrf(response: Response, token: str | None = None) -> str:
    s = get_settings()
    if not (token and verify_csrf(token, "csrf")):
        token = csrf_token_for("csrf")
    response.set_cookie(CSRF_COOKIE, token, max_age=60 * 60 * 12, secure=s.cookie_secure, httponly=False,
                        samesite=s.cookie_samesite, path="/", domain=s.cookie_domain)
    return token


def _set_refresh(response: Response, value: str) -> None:
    s = get_settings()
    response.set_cookie(REFRESH_COOKIE, value, max_age=s.refresh_token_days * 86400, secure=s.cookie_secure,
                        httponly=True, samesite=s.cookie_samesite, path=AUTH_PATH, domain=s.cookie_domain)


def _clear_refresh(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(REFRESH_COOKIE, path=AUTH_PATH, domain=s.cookie_domain, secure=s.cookie_secure,
                           httponly=True, samesite=s.cookie_samesite)


def check_csrf(request: Request) -> None:
    header = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(CSRF_COOKIE)
    if not header or not cookie or header != cookie or not verify_csrf(header, "csrf"):
        raise Forbidden("CSRF verification failed. Reload the page and try again.")
    origin = request.headers.get("origin")
    if origin:
        s = get_settings()
        host = request.headers.get("host", "")
        same_host = origin.split("://", 1)[-1] == host
        if not same_host and origin not in s.cors_origins:
            raise Forbidden("Cross-origin request rejected.")


@router.get("/csrf")
def csrf(request: Request, response: Response):
    return {"csrfToken": _set_csrf(response, request.cookies.get(CSRF_COOKIE))}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_csrf(request)
    s = get_settings()
    ip, ua = client_ip(request), request.headers.get("user-agent")
    db_hit(f"login:ip:{ip}", s.rate_login)
    db_hit(f"login:user:{body.username.lower()[:80]}", s.rate_login)
    user = svc.authenticate(db, body.username, body.password, body.mfa, ip, ua)
    if body.portal:
        roles = set(db.scalars(text("SELECT role_code FROM v_active_user_role WHERE user_id = :u"), {"u": user.user_id}))
        allowed = portals_of(roles, user.is_superuser)
        if body.portal not in allowed:
            audit_login(db, body.username, user.user_id, False, ip, ua, f"wrong portal: {body.portal}")
            db.commit()
            wrong = Forbidden(f"This account cannot sign in through the {PORTALS[body.portal]['label']} portal."
                              + (f" Please use the {PORTALS[allowed[0]]['label']} portal." if allowed else ""))
            wrong.code = "wrong_portal"
            raise wrong
    sess, cookie = svc.start_session(db, user, ip, ua)
    db.commit()
    token, ttl = create_access_token(user.user_id, sess.session_id, user.security_version)
    _set_refresh(response, cookie)
    csrf_value = _set_csrf(response, request.cookies.get(CSRF_COOKIE))
    return {"access": token, "token_type": "bearer", "expires_in": ttl, "csrfToken": csrf_value,
            "must_change_password": user.must_change_password}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    check_csrf(request)
    cookie = request.cookies.get(REFRESH_COOKIE)
    if not cookie:
        raise Unauthorized("Session expired.")
    s = get_settings()
    ip = client_ip(request)
    db_hit(f"refresh:ip:{ip}", s.rate_default)
    try:
        user, sess, new_cookie = svc.rotate_session(db, cookie, ip, request.headers.get("user-agent"))
    except Unauthorized:
        _clear_refresh(response)
        raise
    db.commit()
    token, ttl = create_access_token(user.user_id, sess.session_id, user.security_version)
    _set_refresh(response, new_cookie)
    return {"access": token, "token_type": "bearer", "expires_in": ttl, "csrfToken": _set_csrf(response, request.cookies.get(CSRF_COOKIE))}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    check_csrf(request)
    cookie = request.cookies.get(REFRESH_COOKIE)
    if cookie and "." in cookie:
        svc.revoke_session(db, cookie.split(".", 1)[0])
        db.commit()
    response = Response(status_code=204)
    _clear_refresh(response)
    return response


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    check_csrf(request)
    user = db.get(UserAccount, principal.user_id)
    svc.revoke_all(db, user)
    db.commit()
    forget_principals(principal.user_id)
    response = Response(status_code=204)
    _clear_refresh(response)
    return response


def profile(principal: Principal, db: Session) -> dict:
    user = db.get(UserAccount, principal.user_id)
    grants = [{"code": g.code, "scope_type": g.scope_type, "scope_id": g.scope_id}
              for g in principal.grants if g.effect == "ALLOW"]
    return {
        "user_id": principal.user_id, "username": principal.username, "email": principal.email,
        "full_name": principal.full_name, "is_superuser": principal.is_superuser,
        "must_change_password": principal.must_change_password, "mfa_enabled": bool(user.multi_factor_enabled),
        "groups": principal.role_codes, "roles": principal.role_codes,
        "permissions": principal.allowed_codes(), "access_modules": principal.modules(), "grants": grants,
        "student_ids": sorted(principal.student_ids), "employee_ids": sorted(principal.employee_ids),
        "institution_ids": sorted(principal.institution_ids()),
        "last_login_at": user.last_login_at,
    }


@router.get("/me")
def me(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return profile(principal, db)


@router.post("/change-password")
def change_password(body: PasswordIn, request: Request, response: Response,
                    principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    db_hit(f"pwd:{principal.user_id}", "10/900")
    user = db.get(UserAccount, principal.user_id)
    svc.change_password(db, user, body.current_password, body.new_password)
    sess, cookie = svc.start_session(db, user, client_ip(request), request.headers.get("user-agent"))
    db.commit()
    forget_principals(principal.user_id)
    _set_refresh(response, cookie)  # other devices are signed out; this one gets a fresh session
    token, ttl = create_access_token(user.user_id, sess.session_id, user.security_version)
    return {"access": token, "expires_in": ttl}


@router.get("/sessions")
def sessions(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuthSession).where(
        AuthSession.user_id == principal.user_id, AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.now(UTC)).order_by(AuthSession.last_used_at.desc())).all()
    return {"results": [{"session_id": r.session_id, "created_at": r.created_at, "last_used_at": r.last_used_at,
                         "ip_address": r.ip_address, "user_agent": r.user_agent,
                         "current": r.session_id == principal.session_id} for r in rows]}


@router.delete("/sessions/{session_id}", status_code=204)
def revoke(session_id: str, request: Request, principal: Principal = Depends(current_principal),
           db: Session = Depends(get_db)):
    check_csrf(request)
    if not svc.revoke_session(db, session_id, principal.user_id, "revoked by user"):
        raise NotFound("Session not found.")
    db.commit()
    return Response(status_code=204)


@router.post("/mfa/setup")
def mfa_setup(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = db.get(UserAccount, principal.user_id)
    if user.multi_factor_enabled:
        raise Invalid("Multi-factor authentication is already enabled.")
    user.mfa_secret = totp.new_secret()
    db.commit()
    return {"secret": user.mfa_secret, "otpauth_uri": totp.provisioning_uri(user.mfa_secret, user.username)}


@router.post("/mfa/enable", status_code=204)
def mfa_enable(body: MfaCodeIn, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = db.get(UserAccount, principal.user_id)
    if not user.mfa_secret or not totp.verify(user.mfa_secret, body.code):
        raise Invalid("The verification code is not valid.", details={"code": ["Invalid code."]})
    user.multi_factor_enabled = True
    db.commit()
    return Response(status_code=204)


@router.post("/mfa/disable", status_code=204)
def mfa_disable(body: MfaCodeIn, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = db.get(UserAccount, principal.user_id)
    if not user.multi_factor_enabled:
        return Response(status_code=204)
    if not body.password or not verify_password(body.password, user.password_hash)[0] \
            or not totp.verify(user.mfa_secret or "", body.code):
        raise Invalid("Password or verification code is not valid.")
    user.multi_factor_enabled = False
    user.mfa_secret = None
    db.commit()
    return Response(status_code=204)
