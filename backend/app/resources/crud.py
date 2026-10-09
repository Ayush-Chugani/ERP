"""Generic, scope-aware CRUD over a ResourceSpec. Every query is filtered by the caller's row scope.

Composite resources (a subtype table plus its shared ``staff_activity`` parent) are handled transparently through
``ResourceSpec.base_select`` / ``col`` and the ``Merged`` row wrapper.
"""
import csv
import io
import operator
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import asc, desc, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.rbac.engine import Principal, ScopeSet
from app.rbac.scope import scope_clause
from app.resources import domain_hooks, rules
from app.resources.spec import REGISTRY, Merged, ResourceSpec
from app.services import audit

RESERVED = {"page", "page_size", "search", "ordering", "format"}
OPS = {"eq", "ne", "in", "gte", "lte", "gt", "lt", "isnull", "contains", "startswith"}
MAX_PAGE = 100
EXPORT_LIMIT = 50_000


# --------------------------------------------------------------------------------------------------- row access
def wrap(spec: ResourceSpec, row: Any) -> Any:
    if spec.parent_model is None:
        return row
    sub, parent = row
    return Merged(sub, parent, spec.parent_cols)


def fetch_all(db: Session, spec: ResourceSpec, q) -> list[Any]:
    if spec.parent_model is None:
        return list(db.scalars(q))
    return [wrap(spec, (s, p)) for s, p in db.execute(q)]


def fetch_one(db: Session, spec: ResourceSpec, q) -> Any | None:
    rows = fetch_all(db, spec, q.limit(1))
    return rows[0] if rows else None


# ---------------------------------------------------------------------------------------------------------- scope
def scope_for(spec: ResourceSpec, principal: Principal, action: str) -> ScopeSet:
    """Scope of rows the principal may touch with ``action``; raises Forbidden when none."""
    if spec.perm_module == "IAM" and not principal.is_superuser:
        raise Forbidden()       # accounts and access tables are managed only through /security (which scopes by organisation)
    if spec.public_read and action == "READ":
        return ScopeSet(everything=True)
    scope = principal.scope_for(spec.perm_module, spec.perm_resource, action)
    if scope.empty:
        raise Forbidden()
    return scope


def self_only(spec: ResourceSpec, principal: Principal, action: str) -> bool:
    """True when the caller can perform ``action`` only on their own records (SELF scope, no organisational grant)."""
    if principal.is_superuser:
        return False
    return not principal.scope_for(spec.perm_module, spec.perm_resource, action).organisational


def assignment_clause(spec: ResourceSpec, principal: Principal, action: str):
    """Extra row filter for teaching roles: only assigned classes / papers and mentees (``None`` = no extra restriction)."""
    from sqlalchemy import false, or_

    from app.rbac.matrix import CLASS_ROLES, CLASS_SCOPED, MENTEE_SCOPED, MENTOR_ROLES, MENTORING_OWN, TEACHING_ROLES
    from app.rbac.scope import _classes, attr_exprs

    table = spec.table
    if principal.is_superuser or not (table in CLASS_SCOPED or table in MENTEE_SCOPED or table in MENTORING_OWN):
        return None
    roles = principal.granting_roles(spec.perm_module, spec.perm_resource, action)
    if not roles or not roles <= TEACHING_ROLES:
        return None                                  # someone with a wider role (or a direct grant) is not restricted
    conds = []
    emps = list(principal.employee_ids)
    classes = _classes()
    fca, section, ma = (classes[n].__table__ for n in ("faculty_course_assignment", "course_offering_section", "mentor_assignment"))
    restricted = False
    mentees = select(ma.c.student_id).where(ma.c.employee_id.in_(emps), ma.c.assignment_status == "ACTIVE")
    if table in CLASS_SCOPED:
        restricted = True
        if roles & CLASS_ROLES and emps:
            mine = select(fca.c.course_offering_section_id).where(fca.c.employee_id.in_(emps), fca.c.assignment_status == "ACTIVE")
            sec_exprs = attr_exprs(spec.model, "course_offering_section")
            if sec_exprs:
                conds.extend(e.in_(mine) for e in sec_exprs)
            else:
                offerings = select(section.c.course_offering_id).where(section.c.course_offering_section_id.in_(mine))
                conds.extend(e.in_(offerings) for e in attr_exprs(spec.model, "course_offering"))
        if table in MENTEE_SCOPED and roles & MENTOR_ROLES and emps:
            conds.extend(e.in_(mentees) for e in attr_exprs(spec.model, "student"))
    elif table in MENTEE_SCOPED and roles <= MENTOR_ROLES:
        restricted = True                     # pure mentors / advisors see their mentees only; teachers keep the student list
        if emps:
            conds.extend(e.in_(mentees) for e in attr_exprs(spec.model, "student"))
    if table in MENTORING_OWN:
        restricted = True
        if emps:
            if table == "mentor_assignment":
                conds.append(spec.model.__table__.c.employee_id.in_(emps))
            else:
                own = select(ma.c.mentor_assignment_id).where(ma.c.employee_id.in_(emps))
                conds.extend(e.in_(own) for e in attr_exprs(spec.model, "mentor_assignment"))
    if not restricted:
        return None
    return or_(*conds) if conds else false()


def scoped(spec: ResourceSpec, principal: Principal, action: str):
    scope = scope_for(spec, principal, action)
    clause = scope_clause(spec.model, scope, principal)
    q = spec.base_select()
    if clause is not None:
        q = q.where(clause)
    extra = assignment_clause(spec, principal, action)
    if extra is not None:
        q = q.where(extra)
    if spec.soft_delete:
        q = q.where(spec.col("deleted_at").is_(None))
    if spec.self_filter and action == "READ" and not scope.organisational and not principal.is_superuser:
        q = spec.self_filter(q, spec)
    return q, clause


# -------------------------------------------------------------------------------------------------------- parsing
def _coerce(kind: str, raw: str, name: str) -> Any:
    try:
        if kind == "int":
            return int(raw)
        if kind == "decimal":
            return Decimal(raw)
        if kind == "bool":
            if raw.lower() in ("1", "true", "yes"):
                return True
            if raw.lower() in ("0", "false", "no"):
                return False
            raise ValueError
        if kind == "date":
            return date.fromisoformat(raw)
        if kind == "datetime":
            v = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return v if v.tzinfo else v.replace(tzinfo=UTC)
        if kind == "time":
            return time.fromisoformat(raw)
    except (ValueError, InvalidOperation):
        raise Invalid(f"Invalid value for filter '{name}'.", details={name: ["Invalid value."]}) from None
    return raw


def apply_filters(spec: ResourceSpec, q, params) -> Any:
    for key, raw in params.multi_items():
        if key in RESERVED:
            continue
        name, _, op = key.partition("__")
        op = op or "eq"
        col = spec.columns.get(name)
        if col is None or col.hidden or op not in OPS:
            raise Invalid(f"Unknown filter '{key}'.", details={key: ["Unknown filter."]})
        c = spec.col(name)
        if op == "isnull":
            q = q.where(c.is_(None) if raw.lower() in ("1", "true") else c.is_not(None))
        elif op == "in":
            values = [_coerce(col.kind, v.strip(), key) for v in raw.split(",") if v.strip()][:200]
            q = q.where(c.in_(values))
        elif op in ("contains", "startswith"):
            esc = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            q = q.where(c.ilike(f"%{esc}%" if op == "contains" else f"{esc}%", escape="\\"))
        else:
            v = _coerce(col.kind, raw, key)
            if col.kind == "bool" and op not in ("eq", "ne"):
                raise Invalid(f"Filter '{key}' is not supported for yes/no fields.", details={key: ["Unsupported."]})
            compare = {"eq": operator.eq, "ne": operator.ne, "gte": operator.ge, "lte": operator.le, "gt": operator.gt, "lt": operator.lt}
            q = q.where(compare[op](c, v))
    return q


def apply_search(spec: ResourceSpec, q, term: str | None):
    if not term or not spec.search:
        return q
    esc = term.strip()[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return q.where(or_(*[spec.col(n).ilike(f"%{esc}%", escape="\\") for n in spec.search]))


def apply_ordering(spec: ResourceSpec, q, ordering: str | None):
    names = [o.strip() for o in (ordering or "").split(",") if o.strip()] or spec.order_default
    order = []
    for o in names:
        n = o.lstrip("-")
        col = spec.columns.get(n)
        if col is None or col.hidden:
            raise Invalid(f"Cannot order by '{n}'.", details={"ordering": [f"Unknown field {n}."]})
        order.append(desc(spec.col(n)) if o.startswith("-") else asc(spec.col(n)))
    if spec.pk not in [o.lstrip("-") for o in names]:
        order.append(asc(spec.col(spec.pk)))
    return q.order_by(*order)


# ---------------------------------------------------------------------------------------------------- serialising
def _target_label_expr(table_name: str):
    from app.resources.spec import build_columns, label_columns, table_to_model

    model = table_to_model()[table_name]
    spec = REGISTRY.get(table_name)
    cols = spec.label_cols if spec else label_columns(model.__table__, build_columns(model.__table__))
    t = model.__table__
    pk = list(t.primary_key.columns)[0]
    expr = t.c[cols[0]] if cols else pk
    if table_name == "user_account":
        expr = t.c.username
    return t, pk, expr


def labels_for(db: Session, spec: ResourceSpec, rows: list[Any]) -> list[dict]:
    """Resolve human-readable labels for foreign keys in one query per target table."""
    fk_cols = [c for c in spec.columns.values() if c.fk_table and not c.hidden]
    resolved: dict[tuple[str, Any], str] = {}
    for fk in fk_cols:
        ids = {getattr(r, fk.name) for r in rows if getattr(r, fk.name) is not None}
        if not ids:
            continue
        t, pk, expr = _target_label_expr(fk.fk_table)
        for pk_val, label in db.execute(select(pk, expr).where(pk.in_(ids))):
            resolved[(fk.fk_table, pk_val)] = str(label) if label is not None else str(pk_val)
    out = []
    for r in rows:
        labels = {}
        for fk in fk_cols:
            v = getattr(r, fk.name)
            if v is not None and (fk.fk_table, v) in resolved:
                labels[fk.name] = resolved[(fk.fk_table, v)]
        out.append(labels)
    return out


def status_code(db: Session, spec: ResourceSpec, obj: Any) -> str | None:
    """Current status as a code string (resolving FK-based statuses)."""
    if not spec.status_col:
        return None
    value = getattr(obj, spec.status_col)
    if spec.status_lookup is None or value is None:
        return value
    table, id_col, code_col = spec.status_lookup
    return db.execute(text(f"SELECT {code_col} FROM {table} WHERE {id_col} = :i"), {"i": value}).scalar()


def row_dict(spec: ResourceSpec, obj: Any, labels: dict | None = None, status: str | None = None) -> dict:
    d = {n: getattr(obj, n) for n, c in spec.columns.items() if not c.hidden}
    d["labels"] = labels or {}
    if status is not None:
        d["workflow_status"] = status
    return d


def snapshot(spec: ResourceSpec, obj: Any) -> dict:
    return {n: getattr(obj, n) for n, c in spec.columns.items() if not c.hidden}


# ------------------------------------------------------------------------------------------------- operations
def list_rows(db: Session, spec: ResourceSpec, principal: Principal, params) -> dict:
    q, _ = scoped(spec, principal, "READ")
    q = apply_filters(spec, q, params)
    q = apply_search(spec, q, params.get("search"))
    try:
        page = max(1, int(params.get("page", 1)))
        size = min(MAX_PAGE, max(1, int(params.get("page_size", 25))))
    except ValueError:
        raise Invalid("page and page_size must be integers.") from None
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    q = apply_ordering(spec, q, params.get("ordering")).limit(size).offset((page - 1) * size)
    rows = fetch_all(db, spec, q)
    lab = labels_for(db, spec, rows)
    return {"count": total, "page": page, "page_size": size,
            "next": page + 1 if page * size < total else None, "previous": page - 1 if page > 1 else None,
            "results": [row_dict(spec, r, lab[i], status_code(db, spec, r) if spec.status_lookup else None)
                        for i, r in enumerate(rows)]}


def get_one(db: Session, spec: ResourceSpec, principal: Principal, pk: Any, action: str = "READ", lock: bool = False):
    q, _ = scoped(spec, principal, action)
    q = q.where(spec.col(spec.pk) == pk)
    if lock:
        q = q.with_for_update(of=spec.model)
    obj = fetch_one(db, spec, q)
    if obj is None:
        raise NotFound()
    return obj


def detail(db: Session, spec: ResourceSpec, obj: Any) -> dict:
    return row_dict(spec, obj, labels_for(db, spec, [obj])[0], status_code(db, spec, obj) if spec.status_lookup else None)


def _check_inside_scope(db: Session, spec: ResourceSpec, principal: Principal, action: str, obj: Any) -> None:
    """After a write, the row must still be inside the caller's scope (blocks moving data out of one's remit)."""
    scope = scope_for(spec, principal, action)
    clause = scope_clause(spec.model, scope, principal)
    extra = assignment_clause(spec, principal, action)
    if clause is None and extra is None:
        return
    pk = spec.model.__table__.c[spec.pk]
    conds = [c for c in (clause, extra) if c is not None]
    ok = db.scalar(select(func.count()).select_from(spec.model).where(pk == getattr(obj, spec.pk), *conds))
    if not ok:
        raise Forbidden("The record would fall outside the organisational scope you are allowed to manage.")


def _clean(spec: ResourceSpec, data: dict, creating: bool) -> dict:
    out = {}
    for k, v in data.items():
        col = spec.columns[k]
        if isinstance(v, str):
            v = v.strip()
            if v == "" and col.nullable:
                v = None
        if v == "" and not col.nullable and not (creating and col.has_default):
            raise Invalid(f"{col.label} cannot be empty.", details={k: ["This field is required."]})
        if v is None and not col.nullable:
            if creating and col.has_default:
                continue
            raise Invalid(f"{col.label} cannot be empty.", details={k: ["This field is required."]})
        out[k] = v
    return out


def create_row(db: Session, spec: ResourceSpec, principal: Principal, body, ctx: dict) -> Any:
    if spec.read_only:
        raise Forbidden("This resource is read-only.")
    scope_for(spec, principal, "CREATE")
    if self_only(spec, principal, "CREATE") and not spec.self_create:
        raise Forbidden("You can only create records through your organisation's administrators.")
    data = _clean(spec, body.model_dump(exclude_unset=True), True)
    cols = spec.columns
    if spec.parent_model is not None:
        from app.resources.activity import prepare_activity_create

        if self_only(spec, principal, "CREATE"):
            # Organisation is derived from the employee's assignment, never taken from a self-service caller.
            for k in ("institution_id", "campus_id", "department_id"):
                data.pop(k, None)
        data = prepare_activity_create(db, spec, principal, data)
    if "institution_id" in cols and data.get("institution_id") is None:
        inst = principal.institution_ids()
        if len(inst) == 1:
            data["institution_id"] = next(iter(inst))
    for n, c in cols.items():
        if c.auto_user:
            data[n] = principal.user_id
    for n, c in cols.items():
        if c.initial and data.get(n) is None:
            data[n] = c.initial
    rules.run_before_create(spec, db, principal, data)
    if "version" in cols and spec.versioned and data.get("version") is None and spec.parent_model is None:
        data["version"] = 1
    missing = {n: ["This field is required."] for n, c in cols.items()
               if (c.required or (n == "institution_id" and not c.nullable)) and data.get(n) is None and not c.readonly}
    if missing:
        raise Invalid("Some required values are missing.", details=missing)
    if spec.parent_model is not None:
        ptab, stab = spec.parent_model.__table__, spec.model.__table__
        parent = spec.parent_model(**{k: v for k, v in data.items() if k in ptab.c and (k in spec.parent_cols or k not in stab.c)})
        db.add(parent)
        db.flush()
        pk_value = getattr(parent, spec.pk)
        sub = spec.model(**{k: v for k, v in data.items() if k in stab.c and k not in spec.parent_cols},
                         **{spec.pk: pk_value})
        db.add(sub)
        db.flush()
        obj = Merged(sub, parent, spec.parent_cols)
    else:
        obj = spec.model(**data)
        db.add(obj)
        db.flush()
    _check_inside_scope(db, spec, principal, "CREATE", obj)
    rules.run_after_create(spec, db, principal, obj)
    after = snapshot(spec, obj)
    audit.record(db, principal, action="create", module=spec.perm_module, resource=spec.table,
                 record_id=getattr(obj, spec.pk), after=after, request_id=ctx.get("request_id"), ip=ctx.get("ip"),
                 institution_id=after.get("institution_id"))
    return obj


def _touch(spec: ResourceSpec, obj: Any, principal: Principal) -> None:
    """Record who last changed the row."""
    for name in ("updated_by_id", "updated_by_user_id", "actor_id"):
        if name in spec.columns and spec.columns[name].auto_user or name in spec.parent_cols and name != "actor_id":
            setattr(obj, name, principal.user_id)


def _editable(db: Session, spec: ResourceSpec, principal: Principal, obj: Any) -> None:
    """Approval-governed records are frozen once submitted (only drafts and returned items are editable)."""
    if spec.status_lookup and not principal.is_superuser:
        if status_code(db, spec, obj) not in ("DRAFT", "RETURNED"):
            raise Conflict("This record is locked because it has been submitted. Withdraw or return it to edit.",
                           code="record_locked")


def update_row(db: Session, spec: ResourceSpec, principal: Principal, pk: Any, body, ctx: dict) -> Any:
    if spec.read_only:
        raise Forbidden("This resource is read-only.")
    obj = get_one(db, spec, principal, pk, "UPDATE", lock=True)
    data = body.model_dump(exclude_unset=True)
    version = data.pop("version", None) if spec.versioned else None
    if spec.versioned and version is not None and version != obj.version:
        raise Conflict("This record was changed by someone else. Reload it and try again.", code="stale_version",
                       details={"current_version": obj.version})
    data = _clean(spec, data, False)
    if self_only(spec, principal, "UPDATE"):
        forbidden = sorted(set(data) - spec.self_fields)
        if forbidden:
            raise Forbidden("You may only change: " + (", ".join(sorted(spec.self_fields)) or "nothing on this record")
                            + ".")
    if spec.status_col and spec.status_col in data and data[spec.status_col] != getattr(obj, spec.status_col) \
            and spec.transitions:
        raise Invalid("Use the workflow actions to change the status.", details={spec.status_col: ["Read-only."]})
    _editable(db, spec, principal, obj)
    before = snapshot(spec, obj)
    for k, v in data.items():
        setattr(obj, k, v)
    _touch(spec, obj, principal)
    if spec.versioned:
        obj.version = (obj.version or 0) + 1
    db.flush()
    _check_inside_scope(db, spec, principal, "UPDATE", obj)
    domain_hooks.run_after_update(spec, db, principal, obj)
    b, a = audit.diff(before, snapshot(spec, obj))
    if a:
        audit.record(db, principal, action="update", module=spec.perm_module, resource=spec.table, record_id=pk,
                     before=b, after=a, request_id=ctx.get("request_id"), ip=ctx.get("ip"),
                     institution_id=before.get("institution_id"))
    return obj


def delete_row(db: Session, spec: ResourceSpec, principal: Principal, pk: Any, ctx: dict) -> None:
    if spec.read_only or spec.no_delete:
        raise Forbidden("This resource cannot be deleted.")
    if self_only(spec, principal, "DELETE") and not spec.self_delete:
        raise Forbidden()
    obj = get_one(db, spec, principal, pk, "DELETE", lock=True)
    before = snapshot(spec, obj)
    if spec.status_lookup and not principal.is_superuser and status_code(db, spec, obj) not in (
            "DRAFT", "WITHDRAWN", "REJECTED", "RETURNED"):
        raise Conflict("Only draft, returned, withdrawn or rejected records can be deleted.", code="record_locked")
    if spec.soft_delete:
        obj.deleted_at = datetime.now(UTC)
        for name in ("deleted_by_user_id", "updated_by_id"):
            if name in spec.columns or name in spec.parent_cols:
                setattr(obj, name, principal.user_id)
        db.flush()
    else:
        db.delete(obj.sub if isinstance(obj, Merged) else obj)
        db.flush()
    audit.record(db, principal, action="delete", module=spec.perm_module, resource=spec.table, record_id=pk,
                 before=before, request_id=ctx.get("request_id"), ip=ctx.get("ip"),
                 institution_id=before.get("institution_id"))


def run_transition(db: Session, spec: ResourceSpec, principal: Principal, pk: Any, name: str, remarks: str | None,
                   ctx: dict) -> Any:
    t = spec.transitions.get(name)
    if t is None:
        raise NotFound("Unknown action.")
    if not principal.can(spec.perm_module, spec.perm_resource, t.action) and not principal.is_superuser:
        raise Forbidden()
    obj = get_one(db, spec, principal, pk, t.action, lock=True)
    current = status_code(db, spec, obj)
    if t.from_states and current not in t.from_states:
        raise Conflict(f"This action is not available while the record is {str(current).replace('_', ' ').lower()}.",
                       code="invalid_transition", details={"status": current, "allowed_from": list(t.from_states)})
    if t.remarks == "required" and not (remarks and remarks.strip()):
        raise Invalid("Remarks are required for this action.", details={"remarks": ["Required."]})
    for field in t.requires:
        if getattr(obj, field, None) in (None, ""):
            raise Invalid(f"{spec.columns[field].label} must be filled in first.", details={field: ["Required."]})
    if self_only(spec, principal, t.action) and not t.self_service:
        raise Forbidden("This action is reserved for reviewers.")
    if t.guard:
        t.guard(db, principal, obj)
    before = snapshot(spec, obj)
    if spec.status_lookup:
        table, id_col, code_col = spec.status_lookup
        new_id = db.execute(text(f"SELECT {id_col} FROM {table} WHERE {code_col} = :c"), {"c": t.to_state}).scalar()
        setattr(obj, spec.status_col, new_id)
    else:
        setattr(obj, spec.status_col, t.to_state)
    for k, v in t.set_fields.items():
        setattr(obj, k, datetime.now(UTC) if v == "now" else principal.user_id if v == "user" else v)
    if remarks and t.remarks_field and (t.remarks_field in spec.columns or t.remarks_field in spec.parent_cols):
        setattr(obj, t.remarks_field, remarks.strip()[:1000])
    _touch(spec, obj, principal)
    if spec.versioned:
        obj.version = (obj.version or 0) + 1
    db.flush()
    audit.status_change(db, principal, spec.table, pk, current, t.to_state, name, remarks)
    b, a = audit.diff(before, snapshot(spec, obj))
    audit.record(db, principal, action=name, module=spec.perm_module, resource=spec.table, record_id=pk, before=b,
                 after=a, reason=remarks, request_id=ctx.get("request_id"), ip=ctx.get("ip"),
                 institution_id=before.get("institution_id"))
    if t.after:
        t.after(db, principal, obj)
    return obj


def allowed_actions(db: Session, spec: ResourceSpec, principal: Principal, obj: Any) -> list[dict]:
    if not spec.transitions:
        return []
    current = status_code(db, spec, obj)
    out = []
    only_self = {a: self_only(spec, principal, a) for a in {t.action for t in spec.transitions.values()}}
    for t in spec.transitions.values():
        if t.from_states and current not in t.from_states:
            continue
        if not (principal.is_superuser or principal.can(spec.perm_module, spec.perm_resource, t.action)):
            continue
        if only_self[t.action] and not t.self_service and not principal.is_superuser:
            continue
        out.append({"name": t.name, "label": t.label, "remarks": t.remarks, "danger": t.danger})
    return out


def export_csv(db: Session, spec: ResourceSpec, principal: Principal, params) -> str:
    q, _ = scoped(spec, principal, "EXPORT")
    q = apply_filters(spec, q, params)
    q = apply_search(spec, q, params.get("search"))
    q = apply_ordering(spec, q, params.get("ordering")).limit(EXPORT_LIMIT)
    names = [n for n, c in spec.columns.items() if not c.hidden]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(names)
    for obj in fetch_all(db, spec, q):
        w.writerow([_csv_cell(getattr(obj, n)) for n in names])
    return buf.getvalue()


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    s = v.isoformat() if isinstance(v, (datetime, date, time)) else str(v)
    # Neutralise spreadsheet formula injection.
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s
