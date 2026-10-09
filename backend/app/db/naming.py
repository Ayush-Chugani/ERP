"""Central normalisation of constraint and index names.

The schema descends from a legacy system whose generated names carried milestone tokens (``m5``, ``platform``) and
hash suffixes. Every explicit name is normalised once, here, so names stay readable, schema-wide unique and within
PostgreSQL's 63-character identifier limit — without hand-editing hundreds of declarations.
"""
import hashlib
import re

from sqlalchemy import CheckConstraint, MetaData, UniqueConstraint

LEGACY_TOKEN = re.compile(r"(?<![a-z0-9])(?:m\d{1,2}|platform)_")
MAX = 63


def clean(name: str) -> str:
    cleaned = LEGACY_TOKEN.sub("", name)
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_")
    if len(cleaned) > MAX:
        cleaned = cleaned[: MAX - 7] + "_" + hashlib.md5(name.encode(), usedforsecurity=False).hexdigest()[:6]
    return cleaned


def normalise(metadata: MetaData) -> None:
    taken: set[str] = set()
    for table in metadata.sorted_tables:
        named = [i for i in table.indexes if i.name] + [c for c in table.constraints if c.name and isinstance(c, (CheckConstraint, UniqueConstraint))]
        for obj in named:
            new = clean(str(obj.name))
            base, n = new, 2
            while new in taken:
                new = clean(f"{base}_{n}")
                n += 1
            taken.add(new)
            if new != obj.name:
                obj.name = new
