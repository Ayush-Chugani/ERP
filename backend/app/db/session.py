from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def make_engine(url: str | None = None) -> Engine:
    s = get_settings()
    connect_args: dict = {"connect_timeout": 10, "options": "-c timezone=UTC -c statement_timeout=30000"}
    if s.db_pooler == "transaction":
        # PgBouncer / Supavisor transaction mode cannot hold server-side prepared statements.
        connect_args["prepare_threshold"] = None
        connect_args.pop("options")
    if s.db_ssl_mode:
        connect_args["sslmode"] = s.db_ssl_mode
    target = url or s.database_url
    pool_size, overflow = s.db_pool_size, s.db_max_overflow
    if "pooler.supabase.com" in target and ":5432" in target:
        # Supabase's session-mode pooler allows only ~15 clients in total (API + worker + tools share them); a larger
        # pool makes sign-ins fail with "max clients reached". Cap it; use the transaction pooler (6543) to scale out.
        pool_size, overflow = min(pool_size, 4), min(overflow, 2)
    return create_engine(
        target,
        pool_size=pool_size,
        max_overflow=overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=connect_args,
    )


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:  # pragma: no cover - the test suite installs its own engine
        _engine = make_engine()
        _factory = sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _engine


def set_engine(engine: Engine) -> None:
    """Used by tests to swap the database."""
    global _engine, _factory
    _engine = engine
    _factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _factory is not None
    return _factory


def get_db() -> Iterator[Session]:
    """Request-scoped session. Handlers that write must call ``db.commit()`` before responding so a failed
    commit surfaces as an error response; anything uncommitted is rolled back on close."""
    db = session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
