"""Load packaged seed fixtures into an empty or partially seeded database (never overwrites existing rows)."""
import gzip
import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.base import Base

DATA = Path(__file__).parent / "data"


def dec(v):
    if isinstance(v, dict):
        if "$t" in v:
            raw = v["$t"]
            for fn in (datetime.fromisoformat, date.fromisoformat, time.fromisoformat):
                try:
                    return fn(raw)
                except ValueError:
                    continue
        if "$d" in v:
            return Decimal(v["$d"])
    return v


def read(name: str) -> dict[str, list[dict]]:
    path = DATA / f"{name}.json.gz"
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf8") as f:
        return json.load(f)


def load(db: Session, name: str, only_if_empty: bool = False, transform=None) -> dict[str, int]:
    """Insert fixture rows table by table in dependency order. Existing primary keys are left untouched."""
    data = read(name)
    counts: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        rows = data.get(table.name)
        if not rows:
            continue
        if only_if_empty and db.execute(sa.select(sa.func.count()).select_from(table)).scalar():
            continue
        cols = {c.name: c for c in table.columns}
        batch = []
        for r in rows:
            rec = {k: dec(v) for k, v in r.items() if k in cols}
            if transform:
                rec = transform(table.name, rec)
            batch.append(rec)
        for i in range(0, len(batch), 500):
            db.execute(insert(table).values(batch[i:i + 500]).on_conflict_do_nothing())
        counts[table.name] = len(batch)
    reset_sequences(db)
    return counts


def reset_sequences(db: Session) -> None:
    for table in Base.metadata.sorted_tables:
        for col in table.primary_key.columns:
            if isinstance(col.type, (sa.Integer, sa.BigInteger, sa.SmallInteger)) and col.autoincrement is True:
                db.execute(sa.text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', '{col.name}'), "
                    f"GREATEST((SELECT COALESCE(MAX({col.name}), 0) FROM {table.name}), 1))"))
