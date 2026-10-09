"""Test harness: a throw-away PostgreSQL database, seeded once, with every test isolated in a rolled-back transaction."""
import os

TEST_URL = os.environ.get("SIMS_TEST_DATABASE_URL", "postgresql+psycopg://sims:sims_dev_password@127.0.0.1:54329/sims_test")
# Hard safety stop: the suite drops and recreates the schema, so it may only ever touch *_test databases.
if not TEST_URL.split("?")[0].rsplit("/", 1)[-1].endswith("_test"):
    raise SystemExit("Refusing to run tests: SIMS_TEST_DATABASE_URL must point at a database whose name ends in _test")

os.environ["SIMS_ENV"] = "test"
os.environ["SIMS_DATABASE_URL"] = TEST_URL
os.environ["SIMS_COOKIE_SECURE"] = "false"
os.environ["SIMS_SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789"
os.environ["SIMS_RATE_LOGIN"] = "1000/60"
os.environ["SIMS_RATE_DEFAULT"] = "100000/60"
os.environ["SIMS_ALLOWED_HOSTS"] = "localhost,testserver"
os.environ["SIMS_DOCS_ENABLED"] = "true"
import tempfile  # noqa: E402

os.environ["SIMS_STORAGE_LOCAL_ROOT"] = tempfile.mkdtemp(prefix="sims-test-files-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

DEMO_PASSWORD = "Campus@2026"


@pytest.fixture(scope="session")
def engine():
    from app.db import session as dbs
    from tools.dev_reset import rebuild

    eng = dbs.make_engine(TEST_URL)
    rebuild(eng)
    dbs.set_engine(eng)
    import app.models  # noqa: F401
    from app.db.session import db_session
    from app.rbac import catalogue
    from app.seed import demo, loader

    with db_session() as db:
        loader.load(db, "base", only_if_empty=True)
        catalogue.sync(db)
    demo.load_demo(force=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Each test runs inside an outer transaction; application commits only release a SAVEPOINT."""
    from app.db import session as dbs
    from app.rbac.engine import reset_org_cache

    conn = engine.connect()
    outer = conn.begin()
    factory = sessionmaker(conn, expire_on_commit=False, autoflush=False, join_transaction_mode="create_savepoint")
    previous = dbs._factory
    dbs._factory = factory
    reset_org_cache()
    session = factory()
    yield session
    session.close()
    dbs._factory = previous
    outer.rollback()
    conn.close()


@pytest.fixture(scope="session")
def app(engine):
    from app.main import create_app

    return create_app()


@pytest.fixture(autouse=True)
def _fresh_caches():
    from app.api import deps

    deps.forget_principals()
    yield


class Client:
    """Thin wrapper that signs in and carries bearer + CSRF like the browser client does."""

    def __init__(self, app):
        self.http = TestClient(app, base_url="http://localhost")
        self.csrf = self.http.get("/api/v1/auth/csrf").json()["csrfToken"]

    def login(self, username: str, password: str = DEMO_PASSWORD, expect: int = 200, mfa: str | None = None):
        body = {"username": username, "password": password}
        if mfa:
            body["mfa"] = mfa
        r = self.http.post("/api/v1/auth/login", json=body, headers={"X-CSRF-Token": self.csrf})
        assert r.status_code == expect, r.text
        if r.status_code == 200:
            self.http.headers["Authorization"] = "Bearer " + r.json()["access"]
        return r

    def csrf_headers(self):
        return {"X-CSRF-Token": self.http.cookies.get("sims_csrf") or self.csrf}

    def get(self, url, **kw):
        return self.http.get("/api/v1" + url, **kw)

    def post(self, url, json=None, **kw):
        return self.http.post("/api/v1" + url, json=json, **kw)

    def put(self, url, json=None, **kw):
        return self.http.put("/api/v1" + url, json=json, **kw)

    def patch(self, url, json=None, **kw):
        return self.http.patch("/api/v1" + url, json=json, **kw)

    def delete(self, url, **kw):
        return self.http.delete("/api/v1" + url, **kw)


@pytest.fixture()
def client(app, db):
    return Client(app)


@pytest.fixture()
def as_user(app, db):
    def make(username: str) -> Client:
        c = Client(app)
        c.login(username)
        return c

    return make


@pytest.fixture(autouse=True)
def _ai_off_by_default(monkeypatch):
    """The developer's .env may hold a real AI key; tests must never reach the network or depend on it."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_enabled", False)
    monkeypatch.setattr(get_settings(), "ai_api_key", "")
