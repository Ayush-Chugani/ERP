"""Translate a principal's scopes into SQL row filters for any table, following foreign keys to find the
organisational (institution/campus/department/programme) or personal (student/employee/user) owner of a row."""
from functools import lru_cache

from sqlalchemy import ColumnElement, and_, false, or_, select
from sqlalchemy.orm import DeclarativeBase

from app.db.base import Base
from app.rbac.engine import LEVELS, Principal, ScopeSet

MAX_DEPTH = 3


@lru_cache(maxsize=1)
def _classes() -> dict[str, type[DeclarativeBase]]:
    return {m.local_table.name: m.class_ for m in Base.registry.mappers}


def _pk(table):
    cols = list(table.primary_key.columns)
    return cols[0] if len(cols) == 1 else None


@lru_cache(maxsize=4096)
def _paths(table_name: str, attr: str, depth: int = 0) -> tuple[tuple, ...]:
    """Every way to reach ``attr`` (e.g. 'campus') from a table, nearest first.

    A path is ('col', name) for a direct column or the table's own key, or ('fk', fk_col, target_table, sub_path,
    target_col) for a hop through a foreign key. Rows are in scope when *any* path lands inside the granted scope.
    """
    cls = _classes()[table_name]
    table = cls.__table__
    if table.name == attr:
        pk = _pk(table)
        return (("col", pk.name),) if pk is not None else ()
    found: list[tuple] = []
    if f"{attr}_id" in table.c:
        found.append(("col", f"{attr}_id"))
    if depth < MAX_DEPTH:
        for fk in sorted(table.foreign_keys, key=lambda f: (f.parent.nullable, f.parent.name)):
            if len(fk.constraint.columns) != 1:
                continue
            target = fk.column.table.name
            if target == table_name or target not in _classes():
                continue
            for sub in _paths(target, attr, depth + 1):
                found.append(("fk", fk.parent.name, target, sub, fk.column.name))
    return tuple(found[:8])


def _build(table_name: str, path: tuple) -> ColumnElement:
    table = _classes()[table_name].__table__
    if path[0] == "col":
        return table.c[path[1]]
    _, fk_col, target, sub, target_col = path
    target_table = _classes()[target].__table__
    inner = _build(target, sub)
    return select(inner).where(target_table.c[target_col] == table.c[fk_col]).correlate(table).scalar_subquery()


def attr_exprs(model, attr: str) -> list[ColumnElement]:
    name = model.__table__.name
    return [_build(name, p) for p in _paths(name, attr)]


def has_self_attrs(model) -> bool:
    """True when rows of ``model`` can belong to a person (student, employee or user), i.e. SELF scope can match something."""
    return bool(attr_exprs(model, "student") or attr_exprs(model, "employee") or "user_id" in model.__table__.c)


def scope_clause(model, scope: ScopeSet, principal: Principal) -> ColumnElement | None:
    """Return a WHERE clause limiting ``model`` rows to ``scope``; ``None`` means unrestricted."""
    if scope.everything:
        return None
    conds: list[ColumnElement] = []
    org_attrs = False
    for level in LEVELS:
        exprs = attr_exprs(model, level)
        if not exprs:
            continue
        org_attrs = True
        ids = scope.for_level(level)
        if ids:
            conds.extend(e.in_(ids) for e in exprs)
    if not org_attrs and scope.organisational:
        return None  # global master data: any organisational grant may use it
    if scope.own:
        for attr, ids in (("student", principal.student_ids), ("employee", principal.employee_ids)):
            if ids:
                conds.extend(e.in_(ids) for e in attr_exprs(model, attr))
        table = model.__table__
        if "user_id" in table.c:
            conds.append(table.c.user_id == principal.user_id)
    if not conds:
        return false()
    return or_(*conds) if len(conds) > 1 else and_(conds[0])
