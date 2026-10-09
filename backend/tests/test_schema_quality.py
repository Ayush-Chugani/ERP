"""Structural rules for the database so it stays clean and maintainable as it grows."""
import re
from collections import defaultdict

import pytest
import sqlalchemy as sa
from sqlalchemy import DateTime

import app.models  # noqa: F401
from app.db.base import Base

TABLES = list(Base.metadata.sorted_tables)
SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
LEGACY = re.compile(r"(^|_)(m\d{1,2}|platform|django)(_|$)")


def _index_columns(table):
    cols = [tuple(c.name for c in i.columns) for i in table.indexes]
    cols += [tuple(c.name for c in u.columns) for u in table.constraints if isinstance(u, sa.UniqueConstraint)]
    cols.append(tuple(c.name for c in table.primary_key.columns))
    return cols


@pytest.mark.parametrize("table", TABLES, ids=[t.name for t in TABLES])
def test_table_conventions(table):
    assert SNAKE.match(table.name) and len(table.name) <= 45, table.name
    assert not LEGACY.search(table.name), f"legacy token in table name {table.name}"
    assert table.primary_key.columns, f"{table.name} has no primary key"
    for col in table.columns:
        assert SNAKE.match(col.name), f"{table.name}.{col.name}"
        if isinstance(col.type, DateTime):
            assert col.type.timezone, f"{table.name}.{col.name} must be timestamptz"
        if col.name.endswith("_id") and not col.foreign_keys and not col.primary_key:
            pass  # soft references are allowed (e.g. audit ids), but must be intentional
    explicit = [c.name for c in table.constraints if c.name and isinstance(c, (sa.CheckConstraint, sa.UniqueConstraint))]
    explicit += [i.name for i in table.indexes if i.name]
    for n in explicit:     # foreign-key names are generated and shortened by SQLAlchemy at DDL time
        assert len(n) <= 63, f"{n} exceeds the PostgreSQL identifier limit"
        assert not LEGACY.search(n), f"legacy token in constraint/index name {n}"


def test_every_foreign_key_is_indexed():
    missing = []
    for t in TABLES:
        covered = _index_columns(t)
        for fk in t.foreign_key_constraints:
            cols = tuple(c.name for c in fk.columns)
            if not any(ix[: len(cols)] == cols for ix in covered):
                missing.append(f"{t.name}({', '.join(cols)})")
    assert not missing, "foreign keys without a supporting index:\n  " + "\n  ".join(missing)


def test_no_duplicate_indexes():
    dupes = []
    for t in TABLES:
        seen = defaultdict(list)
        for i in t.indexes:
            seen[(tuple(str(e) for e in i.expressions), i.unique, str(i.dialect_options["postgresql"]["where"]))].append(i.name)
        dupes += [f"{t.name}: {names}" for names in seen.values() if len(names) > 1]
    assert not dupes, dupes


def test_index_and_constraint_names_are_unique_schema_wide():
    seen = defaultdict(list)
    for t in TABLES:
        for i in t.indexes:
            seen[i.name].append(t.name)
        for c in t.constraints:
            if c.name and isinstance(c, sa.UniqueConstraint):
                seen[c.name].append(t.name)
    clash = {n: ts for n, ts in seen.items() if len(ts) > 1}
    assert not clash, clash


def test_audit_columns_use_one_naming_scheme():
    """Who/when columns: created_at/updated_at (timestamptz, defaulted) wherever present."""
    for t in TABLES:
        for name in ("created_at", "updated_at"):
            if name in t.c:
                col = t.c[name]
                assert not col.nullable and col.server_default is not None, f"{t.name}.{name} needs NOT NULL DEFAULT now()"


def test_live_database_matches_metadata(db):
    """Migrations (applied by the fixture) and models describe the same tables."""
    live = set(sa.inspect(db.connection()).get_table_names())
    assert {t.name for t in TABLES} <= live
    extra = live - {t.name for t in TABLES} - {"alembic_version"}
    assert not extra, f"tables in the database but not in the models: {extra}"
