"""Unit tests for the platform primitives: security helpers, settings, errors, sessions, limits, naming, crypto, storage."""
import base64
import hashlib
import json
import sys
import time
import types
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.config import Settings, get_settings
from app.core import crypto, security, totp
from app.core.errors import AppError, Throttled, install_handlers
from app.core.ratelimit import LocalLimiter, db_hit, parse_rate


# ------------------------------------------------------------------------------------------------ security
def django_pbkdf2(password: str, salt="saltsalt", iterations=1000) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${base64.b64encode(dk).decode()}"


def test_legacy_django_hashes_verify_and_request_an_upgrade():
    h = django_pbkdf2("Secret#12345")
    assert security.verify_password("Secret#12345", h) == (True, True)
    assert security.verify_password("wrong", h) == (False, False)
    assert security.verify_password("x", "pbkdf2_sha256$broken") == (False, False)
    assert security.verify_password("x", "pbkdf2_sha256$abc$s$d") == (False, False)


def test_argon2_verify_rehash_and_unknown_user_timing_path():
    h = security.hash_password("Another#Secret1")
    assert h.startswith("$argon2id$") and security.verify_password("Another#Secret1", h) == (True, False)
    assert security.verify_password("nope", h) == (False, False)
    assert security.verify_password("anything", None) == (False, False)
    assert security.verify_password("anything", "not-a-hash") == (False, False)


def test_access_tokens_reject_tampering_expiry_and_wrong_type():
    token, ttl = security.create_access_token(7, "sid-1", 3)
    claims = security.decode_access_token(token)
    assert claims["sub"] == "7" and claims["sid"] == "sid-1" and claims["sv"] == 3 and ttl == get_settings().access_token_minutes * 60
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(token[:-2] + "xx")
    s = get_settings()
    wrong = jwt.encode({"iss": s.jwt_issuer, "sub": "1", "sid": "s", "iat": int(time.time()), "exp": int(time.time()) + 60, "typ": "refresh"}, s.secret_key, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(wrong)
    expired = jwt.encode({"iss": s.jwt_issuer, "sub": "1", "sid": "s", "iat": 1, "exp": 2, "typ": "access"}, s.secret_key, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(expired)
    none_alg = jwt.encode({"sub": "1"}, "", algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(none_alg)


def test_csrf_tokens():
    t = security.csrf_token_for("csrf")
    assert security.verify_csrf(t, "csrf") and not security.verify_csrf(t, "other")
    assert not security.verify_csrf(None, "csrf") and not security.verify_csrf("nodot", "csrf") and not security.verify_csrf("a.b", "csrf")
    assert security.digest("x") == hashlib.sha256(b"x").hexdigest() and len(security.new_token()) > 40


# ------------------------------------------------------------------------------------------------ settings
@pytest.mark.parametrize("overrides,message", [
    ({"secret_key": "short"}, "SIMS_SECRET_KEY"),
    ({"allowed_hosts": ["*"]}, "Wildcard SIMS_ALLOWED_HOSTS"),
    ({"cookie_secure": False}, "COOKIE_SECURE"),
    ({"cors_origins": ["*"]}, "CORS"),
    ({"field_encryption_keys": ""}, "ENCRYPTION_KEYS"),
])
def test_production_refuses_unsafe_settings(overrides, message):
    good = dict(env="production", secret_key="x" * 40, allowed_hosts=["sims.example.org"], cookie_secure=True,
                field_encryption_keys='{"1": "' + base64.b64encode(b"k" * 32).decode() + '"}', fingerprint_key="f" * 40)
    Settings(**good)   # the baseline is valid
    with pytest.raises(ValidationError, match=message):
        Settings(**{**good, **overrides})


def test_list_settings_accept_csv_and_json(monkeypatch):
    monkeypatch.setenv("SIMS_ALLOWED_HOSTS", "a.example, b.example")
    monkeypatch.setenv("SIMS_CORS_ORIGINS", '["https://x.example"]')
    s = Settings()
    assert s.allowed_hosts == ["a.example", "b.example"] and s.cors_origins == ["https://x.example"]
    assert Settings(allowed_hosts=["h"]).allowed_hosts == ["h"]


# -------------------------------------------------------------------------------------------------- errors
def _fake_orig(sqlstate, constraint=None, column=None):
    diag = types.SimpleNamespace(constraint_name=constraint, column_name=column)
    return types.SimpleNamespace(sqlstate=sqlstate, diag=diag)


@pytest.fixture()
def error_app():
    app = FastAPI()
    install_handlers(app)

    @app.get("/integrity/{state}")
    def integrity(state: str):
        raise IntegrityError("stmt", {}, _fake_orig(state, "ck_rule", "colx"))

    @app.get("/dbapi/{state}")
    def dbapi(state: str):
        raise DBAPIError("stmt", {}, _fake_orig(state))

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    @app.get("/custom")
    def custom():
        raise AppError("teapot", code="short_and_stout", status=418, details={"a": 1})

    @app.get("/typed/{n}")
    def typed(n: int):
        return {"n": n}

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("state,status,code", [("23505", 409, "duplicate"), ("23503", 409, "in_use"), ("23502", 422, "validation_error"),
                                               ("23514", 422, "validation_error"), ("23000", 409, "integrity_error")])
def test_integrity_errors_become_friendly_envelopes(error_app, state, status, code):
    r = error_app.get(f"/integrity/{state}")
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert "stmt" not in r.text and "SELECT" not in r.text


def test_database_and_unexpected_errors_never_leak(error_app):
    assert error_app.get("/dbapi/23001").json()["error"]["code"] == "append_only"
    r = error_app.get("/dbapi/XX000")
    assert r.status_code == 500 and r.json()["error"]["code"] == "server_error"
    boom = error_app.get("/boom")
    assert boom.status_code == 500 and "secret internal detail" not in boom.text
    c = error_app.get("/custom")
    assert c.status_code == 418 and c.json()["error"] == {"code": "short_and_stout", "message": "teapot", "details": {"a": 1}}
    v = error_app.get("/typed/abc")
    assert v.status_code == 422 and v.json()["error"]["code"] == "validation_error" and "n" in v.json()["error"]["details"]
    assert error_app.get("/nope").json()["error"]["code"] == "not_found"
    assert error_app.post("/typed/1").json()["error"]["code"] == "method_not_allowed"


# ------------------------------------------------------------------------------------ rate limits & sessions
def test_rate_spec_parsing_and_local_limiter_window():
    assert parse_rate("10/60") == (10, 60)
    lim = LocalLimiter()
    for _ in range(3):
        lim.hit("k", "3/60")
    with pytest.raises(Throttled) as e:
        lim.hit("k", "3/60")
    assert e.value.details["retry_after"] >= 1
    lim.hit("other", "3/60")
    lim._last_sweep -= 1000
    lim._hits["stale"].append(time.monotonic() - 10_000)
    lim.hit("k2", "3/60")
    assert "stale" not in lim._hits


def test_shared_database_limiter(db):
    for _ in range(3):
        db_hit("unit-test-bucket", "3/600")
    with pytest.raises(Throttled):
        db_hit("unit-test-bucket", "3/600")


def test_engine_options_for_pooler_and_ssl(monkeypatch):
    from app.db.session import make_engine

    s = get_settings()
    monkeypatch.setattr(s, "db_pooler", "transaction")
    monkeypatch.setattr(s, "db_ssl_mode", "require")
    eng = make_engine("postgresql+psycopg://u:p@localhost:6543/db")
    assert eng.dialect.name == "postgresql"
    eng.dispose()


def test_get_db_rolls_back_on_errors(engine):
    from app.db import session as dbs

    gen = dbs.get_db()
    session = next(gen)
    session.execute(sa.text("SELECT 1"))
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("handler failed"))
    with pytest.raises(RuntimeError):
        with dbs.db_session():
            raise RuntimeError("fails")


# ----------------------------------------------------------------------------------------------- naming
def test_constraint_names_are_normalised():
    from app.db.naming import clean

    assert clean("ck_student_m5_student_status") == "ck_student_student_status"
    assert clean("uq_platform_m8_plan_name") == "uq_plan_name"
    long = clean("ix_" + "a" * 100)
    assert len(long) <= 63 and clean("ix_" + "a" * 100) == long


def test_normalise_deduplicates_clashes():
    from sqlalchemy import Column, Index, Integer, MetaData, Table

    from app.db.naming import normalise

    md = MetaData()
    a = Table("a", md, Column("id", Integer, primary_key=True), Column("x", Integer))
    b = Table("b", md, Column("id", Integer, primary_key=True), Column("x", Integer))
    Index("ix_same", a.c.x)
    Index("ix_m5_same", b.c.x)
    normalise(md)
    names = {i.name for t in md.tables.values() for i in t.indexes}
    assert len(names) == 2


# ----------------------------------------------------------------------------------------- crypto / totp
def test_key_rotation_keeps_old_ciphertext_readable(monkeypatch):
    s = get_settings()
    old = base64.b64encode(b"o" * 32).decode()
    new = base64.b64encode(b"n" * 32).decode()
    monkeypatch.setattr(s, "field_encryption_keys", json.dumps({"1": old}))
    monkeypatch.setattr(s, "field_encryption_active", "1")
    blob = crypto.encrypt("123456789012")
    monkeypatch.setattr(s, "field_encryption_keys", json.dumps({"1": old, "2": new}))
    monkeypatch.setattr(s, "field_encryption_active", "2")
    assert crypto.decrypt(blob) == "123456789012"
    assert crypto.decrypt(crypto.encrypt("x")) == "x" and crypto.encrypt("x")[1:2] == b"2"
    monkeypatch.setattr(s, "field_encryption_active", "9")          # unknown active version falls back safely
    assert crypto.decrypt(crypto.encrypt("y")) == "y"


def test_totp_rfc_vector_and_window():
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp._code(secret, 59 // 30) == "287082"                 # RFC 6238 test vector (truncated to 6 digits)
    assert totp.verify(secret, "287082", at=59) and not totp.verify(secret, "287082", at=59 + 300)
    assert not totp.verify(secret, "12345") and not totp.verify(secret, "abcdef") and not totp.verify(secret, "")
    assert totp.provisioning_uri("ABC", "a b").startswith("otpauth://totp/SIMS:a%20b?secret=ABC")
    assert len(totp.new_secret()) >= 32


# ------------------------------------------------------------------------------------------------ storage
def test_local_storage_blocks_path_traversal(tmp_path):
    from app.storage import LocalStorage

    st = LocalStorage(str(tmp_path))
    st.put("a/b.bin", b"data", "application/octet-stream")
    assert st.get("a/b.bin") == b"data"
    st.delete("a/b.bin")
    st.delete("a/b.bin")                                            # idempotent
    with pytest.raises(FileNotFoundError):
        st.get("a/b.bin")
    for bad in ("../escape", "a/../../escape", "/etc/passwd"):
        with pytest.raises(ValueError):
            st.put(bad, b"x", "text/plain")


def test_s3_storage_uses_the_configured_bucket(monkeypatch):
    calls = []

    class Fake:
        def put_object(self, **kw):
            calls.append(("put", kw))

        def get_object(self, **kw):
            return {"Body": types.SimpleNamespace(read=lambda: b"bytes")}

        def delete_object(self, **kw):
            calls.append(("delete", kw))

    fake_boto = types.SimpleNamespace(client=lambda *a, **kw: Fake())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto)
    s = get_settings()
    monkeypatch.setattr(s, "storage_s3_bucket", "private-bucket")
    from app import storage

    st = storage.S3Storage()
    st.put("k", b"v", "text/plain")
    assert st.get("k") == b"bytes"
    st.delete("k")
    assert calls[0][1]["Bucket"] == "private-bucket" and calls[1][0] == "delete"
    monkeypatch.setattr(s, "storage_backend", "s3")
    storage.set_storage(None)
    assert isinstance(storage.get_storage(), storage.S3Storage)
    monkeypatch.setattr(s, "storage_backend", "local")
    storage.set_storage(None)
    assert isinstance(storage.get_storage(), storage.LocalStorage)


# ----------------------------------------------------------------------------------------------- audit
def test_audit_helpers():
    from app.services.audit import diff, jsonable

    assert jsonable({"d": datetime(2026, 1, 2, tzinfo=UTC).date(), "t": datetime(2026, 1, 2, 3, tzinfo=UTC).time(), "n": __import__("decimal").Decimal("1.5"),
                     "l": [1, {"x": datetime(2026, 1, 1, tzinfo=UTC)}], "s": {1}}) == {
        "d": "2026-01-02", "t": "03:00:00", "n": "1.5", "l": [1, {"x": "2026-01-01T00:00:00+00:00"}], "s": [1]}
    assert diff(None, {"a": 1}) == (None, {"a": 1}) and diff({"a": 1}, None) == ({"a": 1}, None)
    assert diff({"a": 1, "b": 2}, {"a": 1, "b": 3}) == ({"b": 2}, {"b": 3})
    assert (datetime.now(UTC) - timedelta(seconds=1)) < datetime.now(UTC)
