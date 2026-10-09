"""Introspect SQLAlchemy models into resource specifications that drive the generic API, validation and UI metadata."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field, create_model
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base

HIDDEN_NAME = re.compile(r"(password|secret|token_hash|_hash$|^hash$|digest|encrypted|ciphertext|fingerprint)", re.I)
AUTO_USER = re.compile(r"(^actor_id$|^created_by(_id|_user_id)$|^updated_by(_id|_user_id)$|^requested_by_id$|^uploaded_by_user_id$|^marked_by_user_id$)")
MANAGED = {"created_at", "updated_at", "created_by_id", "updated_by_id", "deleted_at", "version"}
IN_RE = re.compile(r"^\(*\s*(\w+)\s+IN\s*\((.*?)\)\s*\)*$", re.I | re.S)


@dataclass
class ColumnSpec:
    name: str
    kind: str                          # string text int decimal bool date datetime time json enum
    required: bool
    nullable: bool
    readonly: bool
    max_length: int | None = None
    choices: list[str] | None = None
    fk_table: str | None = None
    label: str = ""
    has_default: bool = False
    pk: bool = False
    hidden: bool = False
    auto_user: bool = False            # filled from the signed-in user, never accepted from the caller
    initial: str | None = None         # starting value for a required status column the caller may omit


@dataclass
class Transition:
    name: str
    label: str
    from_states: tuple[str, ...]
    to_state: str
    action: str = "UPDATE"             # RBAC action required
    remarks: Literal["none", "optional", "required"] = "optional"
    set_fields: dict[str, Any] = field(default_factory=dict)   # field -> value | "now" | "user"
    requires: tuple[str, ...] = ()     # columns that must be non-null before the transition
    danger: bool = False
    self_service: bool = False         # the record's owner may run it even with SELF-only permission
    remarks_field: str | None = None   # column that stores the remarks text
    guard: Any = None                  # callable(db, principal, obj) -> raises to veto
    after: Any = None                  # callable(db, principal, obj) side effects (e.g. enqueue a notification)


@dataclass
class ResourceSpec:
    table: str
    model: type
    slug: str
    module_slug: str
    perm_module: str
    perm_resource: str
    title: str
    group: str
    pk: str
    columns: dict[str, ColumnSpec]
    search: list[str]
    label_cols: list[str]
    order_default: list[str]
    read_only: bool = False
    public_read: bool = False
    status_col: str | None = None
    transitions: dict[str, Transition] = field(default_factory=dict)
    soft_delete: bool = False
    versioned: bool = False
    no_delete: bool = False
    self_create: bool = False          # SELF-scoped principals may create rows (ownership is verified by scope)
    self_fields: frozenset[str] = frozenset()   # fields a SELF-scoped principal may change on update
    self_delete: bool = False
    self_filter: Any = None            # callable(q, spec) narrowing what SELF-scoped readers may see (e.g. published only)
    list_cols: list[str] = field(default_factory=list)
    parent_model: Any = None           # composite resources: row = subtype table + shared parent row
    parent_cols: frozenset[str] = frozenset()
    parent_input: tuple[str, ...] = ()
    activity_type_code: str | None = None
    status_lookup: tuple[str, str, str] | None = None   # (table, id column, code column) when status is a FK
    create_model: Any = None
    update_model: Any = None
    out_model: Any = None

    def col(self, name: str):
        if self.parent_model is not None and name in self.parent_cols:
            return self.parent_model.__table__.c[name]
        return self.model.__table__.c[name]

    def base_select(self):
        from sqlalchemy import select

        if self.parent_model is None:
            return select(self.model)
        sub, par = self.model.__table__, self.parent_model.__table__
        return select(self.model, self.parent_model).join(self.parent_model, sub.c[self.pk] == par.c[self.pk])

    @property
    def path(self) -> str:
        return f"{self.module_slug}/{self.slug}"


class Merged:
    """A subtype row and its parent row presented as one record."""

    __slots__ = ("sub", "parent", "_pcols")

    def __init__(self, sub: Any, parent: Any, pcols: frozenset[str]):
        object.__setattr__(self, "sub", sub)
        object.__setattr__(self, "parent", parent)
        object.__setattr__(self, "_pcols", pcols)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.parent if name in self._pcols else self.sub, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self.parent if name in self._pcols else self.sub, name, value)


def humanize(name: str) -> str:
    base = re.sub(r"_id$", "", name).replace("_", " ").strip()
    return base[:1].upper() + base[1:] if base else name


def _kind(col) -> str:
    t = col.type
    if isinstance(t, Boolean):
        return "bool"
    if isinstance(t, (Integer, BigInteger, SmallInteger)):
        return "int"
    if isinstance(t, Numeric):
        return "decimal"
    if isinstance(t, DateTime):
        return "datetime"
    if isinstance(t, Date):
        return "date"
    if isinstance(t, Time):
        return "time"
    if isinstance(t, JSONB):
        return "json"
    if isinstance(t, Text):
        return "text"
    if isinstance(t, String):
        return "string"
    if isinstance(t, LargeBinary):
        return "binary"
    return "string"


LIST_RE = re.compile(r"^(?:\s*'(?:[^']|'')*'\s*,?)+$")


def _choices(table) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in table.constraints:
        if isinstance(c, CheckConstraint):
            m = IN_RE.match(str(c.sqltext).strip())
            if m and m.group(1) in table.c and LIST_RE.match(m.group(2)):
                out[m.group(1)] = [v.replace("''", "'") for v in re.findall(r"'((?:[^']|'')*)'", m.group(2))]
    return out


def build_columns(table) -> dict[str, ColumnSpec]:
    choices = _choices(table)
    fks = {fk.parent.name: fk.column.table.name for fk in table.foreign_keys if len(fk.constraint.columns) == 1}
    cols: dict[str, ColumnSpec] = {}
    for col in table.columns:
        kind = _kind(col)
        if kind == "binary":
            continue
        computed = isinstance(col.computed, Computed) or col.computed is not None
        has_default = col.server_default is not None or col.default is not None or bool(col.computed)
        pk_auto = col.primary_key and col.autoincrement is True
        readonly = bool(pk_auto or computed or col.name in MANAGED)
        required = (not col.nullable) and not has_default and not readonly
        spec = ColumnSpec(
            name=col.name, kind="enum" if col.name in choices else kind, required=required, nullable=bool(col.nullable),
            readonly=readonly, max_length=getattr(col.type, "length", None), choices=choices.get(col.name),
            fk_table=fks.get(col.name), label=humanize(col.name), has_default=has_default, pk=col.primary_key,
            hidden=bool(HIDDEN_NAME.search(col.name)),
        )
        if col.name == "institution_id" and spec.required:
            spec.required = False        # defaulted from the caller's organisation; enforced in create_row
        if fks.get(col.name) == "user_account" and AUTO_USER.search(col.name):
            spec.auto_user, spec.readonly, spec.required = True, True, False
        if spec.kind == "enum" and spec.choices and spec.required and re.search(r"(status|state)$", col.name):
            spec.required, spec.initial = False, spec.choices[0]
        cols[col.name] = spec
    return cols


PY_TYPES: dict[str, Any] = {"string": str, "text": str, "int": int, "decimal": Decimal, "bool": bool, "date": date,
                            "datetime": datetime, "time": time, "json": Any}


def build_models(spec: ResourceSpec) -> None:
    create_fields: dict[str, Any] = {}
    update_fields: dict[str, Any] = {}
    out_fields: dict[str, Any] = {}
    cls = spec.model.__name__
    for c in spec.columns.values():
        if c.hidden:
            continue
        py: Any = Literal[tuple(c.choices)] if c.kind == "enum" and c.choices else PY_TYPES[c.kind]
        kwargs: dict[str, Any] = {}
        if c.kind in ("string", "text"):
            kwargs["max_length"] = c.max_length or 20000
        out_fields[c.name] = (py | None, Field(default=None))
        if c.readonly:
            continue
        if c.required:
            create_fields[c.name] = (py, Field(..., **kwargs))
        else:
            create_fields[c.name] = (py | None, Field(default=None, **kwargs))
        update_fields[c.name] = (py | None, Field(default=None, **kwargs))
    cfg = ConfigDict(extra="forbid", str_strip_whitespace=True)
    if spec.versioned:
        update_fields["version"] = (int | None, Field(default=None))
    spec.create_model = create_model(f"{cls}Create", __config__=cfg, **create_fields)
    spec.update_model = create_model(f"{cls}Update", __config__=cfg, **update_fields)
    spec.out_model = create_model(f"{cls}Out", __config__=ConfigDict(extra="ignore", from_attributes=True), **out_fields)


def label_columns(table, cols: dict[str, ColumnSpec]) -> list[str]:
    names = list(cols)
    for pattern in (r"^display_name$", r"^name$", r"^title$", r"_name$", r"_title$", r"_number$", r"_code$", r"^username$"):
        hit = [n for n in names if re.search(pattern, n) and cols[n].kind in ("string", "text") and not cols[n].hidden]
        if hit:
            return hit[:1]
    pk = [n for n in names if cols[n].pk]
    return pk[:1] or names[:1]


def search_columns(cols: dict[str, ColumnSpec]) -> list[str]:
    pref = [n for n, c in cols.items() if c.kind == "string" and not c.hidden and not c.fk_table and
            re.search(r"(name|code|title|number|email|phone|reference|subject|description|remarks)", n)]
    if not pref:
        pref = [n for n, c in cols.items() if c.kind == "string" and not c.hidden][:3]
    return pref[:8]


REGISTRY: dict[str, ResourceSpec] = {}   # keyed by table name
BY_PATH: dict[str, ResourceSpec] = {}    # keyed by "module/slug"


def table_to_model() -> dict[str, type]:
    return {m.local_table.name: m.class_ for m in Base.registry.mappers}
