"""Developer helper: rebuild a database from the models (no migrations) and apply the view/trigger/RLS migration.

    SIMS_DATABASE_URL=postgresql+psycopg://... uv run python -m tools.dev_reset
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import make_engine


def rebuild(engine=None) -> None:
    engine = engine or make_engine()
    with engine.begin() as c:
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0002_views_triggers_rls.py"
    spec = importlib.util.spec_from_file_location("post_schema", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with engine.begin() as c:
        for sql in mod.VIEWS:
            c.execute(sa.text(sql))
        c.execute(sa.text("""CREATE OR REPLACE FUNCTION sims_forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Table % is append-only', TG_TABLE_NAME USING ERRCODE = 'restrict_violation'; END $$"""))
        for t in mod.IMMUTABLE_TABLES:
            c.execute(sa.text(f"CREATE TRIGGER trg_{t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                              "FOR EACH ROW EXECUTE FUNCTION sims_forbid_change()"))
        c.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        c.execute(sa.text("INSERT INTO alembic_version VALUES ('0002')"))
        c.execute(sa.text(mod.RLS))


if __name__ == "__main__":
    rebuild()
    print("database rebuilt")
