"""Password hashing, JWT access tokens and opaque refresh tokens."""
import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings

_ph = PasswordHasher()  # argon2id with library defaults (RFC 9106 low-memory profile)
_DUMMY_HASH = _ph.hash("dummy-password-for-timing-equalisation")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def _verify_pbkdf2(password: str, encoded: str) -> bool:
    """Verify a legacy Django ``pbkdf2_sha256$iterations$salt$hash`` value so existing users keep their password."""
    try:
        _, iterations, salt, digest = encoded.split("$", 3)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(base64.b64encode(derived).decode().strip(), digest.strip())
    except (ValueError, TypeError):
        return False


def verify_password(password: str, encoded: str | None) -> tuple[bool, bool]:
    """Return ``(valid, needs_rehash)``. Always spends comparable time, even for unknown users."""
    if not encoded:
        try:
            _ph.verify(_DUMMY_HASH, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            pass
        return False, False
    if encoded.startswith("pbkdf2_sha256$"):
        ok = _verify_pbkdf2(password, encoded)
        return ok, ok
    try:
        _ph.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False
    return True, _ph.check_needs_rehash(encoded)


def new_token(nbytes: int = 48) -> str:
    return secrets.token_urlsafe(nbytes)


def digest(value: str) -> str:
    """Deterministic hash for opaque tokens stored server-side (never store tokens in clear)."""
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(user_id: int, session_id: str, security_version: int) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.access_token_minutes)
    payload: dict[str, Any] = {
        "iss": s.jwt_issuer, "sub": str(user_id), "sid": session_id, "sv": security_version,
        "iat": int(now.timestamp()), "exp": int(exp.timestamp()), "typ": "access", "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.secret_key, algorithm="HS256"), s.access_token_minutes * 60


def decode_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    claims = jwt.decode(
        token, s.secret_key, algorithms=["HS256"], issuer=s.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "sid", "iss"]},
    )
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return claims


def csrf_token_for(session_marker: str) -> str:
    """Signed double-submit CSRF token bound to the refresh cookie (or an anonymous nonce)."""
    s = get_settings()
    nonce = secrets.token_urlsafe(16)
    sig = hmac.new(s.secret_key.encode(), f"{nonce}.{session_marker}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{nonce}.{sig}"


def verify_csrf(token: str | None, session_marker: str) -> bool:
    if not token or "." not in token:
        return False
    s = get_settings()
    nonce, sig = token.split(".", 1)
    good = hmac.new(s.secret_key.encode(), f"{nonce}.{session_marker}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(sig, good)
