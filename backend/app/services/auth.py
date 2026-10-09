"""Authentication domain logic: credential checks, lockout, rotating refresh sessions, password policy."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import totp
from app.core.errors import Invalid, Unauthorized
from app.core.security import digest, hash_password, new_token, verify_password
from app.models.accounts import UserAccount
from app.models.identity_access import LoginAudit, PasswordHistory
from app.models.platform import AuthSession

GENERIC_FAILURE = "Unable to sign in. Check your credentials and try again."
COMMON_PASSWORDS = {
    "password", "password1", "password123", "123456789012", "qwertyuiop12", "admin123456", "welcome12345",
    "letmein12345", "iloveyou1234", "changeme1234", "sims12345678", "administrator",
}


def now() -> datetime:
    return datetime.now(UTC)


def validate_password(password: str, user: UserAccount | None = None, db: Session | None = None) -> None:
    s = get_settings()
    problems: list[str] = []
    if len(password) < s.password_min_length:
        problems.append(f"Use at least {s.password_min_length} characters.")
    if len(password) > 128:
        problems.append("Use at most 128 characters.")
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or len(set(password)) < 5:
        problems.append("This password is too common or too repetitive.")
    if user is not None:
        for part in (user.username, user.email.split("@")[0] if user.email else ""):
            if part and len(part) >= 4 and part.lower() in lowered:
                problems.append("The password must not contain your username or email name.")
                break
        if db is not None and s.password_history:
            recent = db.scalars(select(PasswordHistory.password_hash).where(PasswordHistory.user_id == user.user_id)
                                .order_by(PasswordHistory.changed_at.desc()).limit(s.password_history)).all()
            for old in [user.password_hash, *recent]:
                if verify_password(password, old)[0]:
                    problems.append(f"Do not reuse your last {s.password_history} passwords.")
                    break
    classes = sum(bool(any(f(c) for c in password)) for f in (str.islower, str.isupper, str.isdigit,
                                                              lambda c: not c.isalnum()))
    if classes < 3:
        problems.append("Mix at least three of: lowercase, uppercase, digits, symbols.")
    if problems:
        raise Invalid("The password does not meet the policy.", details={"password": problems})


def audit_login(db: Session, username: str, user_id: int | None, ok: bool, ip: str | None, ua: str | None,
                reason: str | None = None, session_id: str | None = None) -> None:
    db.add(LoginAudit(username_attempted=username[:100], login_at=now(), ip_address=ip, user_agent=(ua or "")[:500],
                      was_successful=ok, failure_reason=reason, session_identifier=session_id, user_id=user_id))


def authenticate(db: Session, username: str, password: str, mfa: str | None, ip: str | None,
                 ua: str | None) -> UserAccount:
    s = get_settings()
    user = db.scalar(select(UserAccount).where(UserAccount.username.ilike(username.strip())).with_for_update())
    valid, rehash = verify_password(password, user.password_hash if user else None)
    when = now()
    if user is None:
        audit_login(db, username, None, False, ip, ua, "unknown user")
        db.commit()
        raise Unauthorized(GENERIC_FAILURE)
    if user.locked_until and user.locked_until > when:
        audit_login(db, username, user.user_id, False, ip, ua, "locked")
        db.commit()
        raise Unauthorized(GENERIC_FAILURE)
    if not valid or not user.is_active or user.account_status not in ("ACTIVE",):
        reason = "bad password" if not valid else f"account {user.account_status.lower()}"
        if not valid:
            user.failed_login_count += 1
            if user.failed_login_count >= s.login_max_failures:
                user.locked_until = when + timedelta(minutes=s.login_lock_minutes)
                user.failed_login_count = 0
                reason = "locked after repeated failures"
        audit_login(db, username, user.user_id, False, ip, ua, reason)
        db.commit()
        raise Unauthorized(GENERIC_FAILURE)
    if user.multi_factor_enabled:
        if not mfa or not user.mfa_secret or not totp.verify(user.mfa_secret, mfa):
            audit_login(db, username, user.user_id, False, ip, ua, "mfa failed")
            db.commit()
            raise Unauthorized("A valid verification code is required." if not mfa else GENERIC_FAILURE)
    if rehash:
        user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = when
    return user


def start_session(db: Session, user: UserAccount, ip: str | None, ua: str | None) -> tuple[AuthSession, str]:
    s = get_settings()
    secret = new_token()
    when = now()
    sess = AuthSession(
        user_id=user.user_id, refresh_digest=digest(secret), created_at=when, last_used_at=when,
        expires_at=when + timedelta(days=s.refresh_token_days), idle_expires_at=when + timedelta(days=s.refresh_idle_days),
        ip_address=ip, user_agent=(ua or "")[:300])
    db.add(sess)
    db.flush()
    audit_login(db, user.username, user.user_id, True, ip, ua, None, sess.session_id)
    return sess, f"{sess.session_id}.{secret}"


def _revoke(sess: AuthSession, reason: str) -> None:
    sess.revoked_at = now()
    sess.revoke_reason = reason


def rotate_session(db: Session, cookie_value: str, ip: str | None, ua: str | None) -> tuple[UserAccount, AuthSession, str]:
    """Validate a refresh cookie and rotate its secret. Reuse of an already-rotated secret revokes the session."""
    s = get_settings()
    try:
        sid, secret = cookie_value.split(".", 1)
        uuid.UUID(sid)
    except ValueError:
        raise Unauthorized("Session expired.") from None
    sess = db.scalar(select(AuthSession).where(AuthSession.session_id == sid).with_for_update())
    if sess is None:
        raise Unauthorized("Session expired.")
    when = now()
    presented = digest(secret)
    if sess.revoked_at is not None:
        raise Unauthorized("Session expired.")
    if sess.previous_digest and presented == sess.previous_digest and presented != sess.refresh_digest:
        _revoke(sess, "refresh token reuse")
        db.commit()
        raise Unauthorized("Session expired.")
    if presented != sess.refresh_digest:
        raise Unauthorized("Session expired.")
    if sess.expires_at <= when or sess.idle_expires_at <= when:
        _revoke(sess, "expired")
        db.commit()
        raise Unauthorized("Session expired.")
    user = db.get(UserAccount, sess.user_id)
    if user is None or not user.is_active or user.account_status != "ACTIVE":
        _revoke(sess, "account disabled")
        db.commit()
        raise Unauthorized("Session expired.")
    new_secret = new_token()
    sess.previous_digest = sess.refresh_digest
    sess.refresh_digest = digest(new_secret)
    sess.rotated_at = when
    sess.rotation_count += 1
    sess.last_used_at = when
    sess.idle_expires_at = min(when + timedelta(days=s.refresh_idle_days), sess.expires_at)
    sess.ip_address, sess.user_agent = ip, (ua or "")[:300]
    return user, sess, f"{sess.session_id}.{new_secret}"


def revoke_session(db: Session, session_id: str, user_id: int | None = None, reason: str = "logout") -> bool:
    q = select(AuthSession).where(AuthSession.session_id == session_id, AuthSession.revoked_at.is_(None))
    if user_id is not None:
        q = q.where(AuthSession.user_id == user_id)
    sess = db.scalar(q)
    if sess is None:
        return False
    _revoke(sess, reason)
    return True


def revoke_all(db: Session, user: UserAccount, reason: str = "logout all") -> None:
    db.execute(update(AuthSession).where(AuthSession.user_id == user.user_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=now(), revoke_reason=reason))
    user.security_version += 1


def change_password(db: Session, user: UserAccount, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash)[0]:
        raise Invalid("The current password is incorrect.", details={"current_password": ["Incorrect password."]})
    set_password(db, user, new)


def set_password(db: Session, user: UserAccount, new: str, must_change: bool = False) -> None:
    validate_password(new, user, db)
    db.add(PasswordHistory(user_id=user.user_id, password_hash=user.password_hash, changed_at=now()))
    user.password_hash = hash_password(new)
    user.password_changed_at = now()
    user.must_change_password = must_change
    user.security_version += 1
    db.execute(update(AuthSession).where(AuthSession.user_id == user.user_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=now(), revoke_reason="password changed"))
