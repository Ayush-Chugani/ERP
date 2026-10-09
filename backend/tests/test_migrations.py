"""The migration chain must build the same schema as the models, from nothing, and be safe on Supabase."""
import os

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from tests.conftest import TEST_URL


@pytest.fixture()
def blank_database():
    base, name = TEST_URL.split("?")[0].rsplit("/", 1)
    target = f"{name.removesuffix('_test')}_migrations_test"
    admin = sa.create_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text(f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE)'))
        c.execute(sa.text(f'CREATE DATABASE "{target}"'))
    url = f"{base}/{target}"
    yield url
    with admin.connect() as c:
        c.execute(sa.text(f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE)'))
    admin.dispose()


def test_migrations_build_the_current_schema_and_are_reversible(blank_database, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "database_url", blank_database)
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")
    command.check(cfg)                                    # models and migrations agree
    eng = sa.create_engine(blank_database)
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity")).scalar() == 0
        assert c.execute(sa.text("SELECT count(*) FROM pg_views WHERE schemaname='public' AND viewname LIKE 'v\\_%'")).scalar() == 3
        assert c.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0004"
    command.downgrade(cfg, "base")
    with eng.connect() as c:
        left = c.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")).scalars().all()
        assert left == []
    eng.dispose()
