"""UI metadata (what the signed-in user may see/do) and foreign-key lookups."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import active_principal
from app.core.errors import Forbidden, NotFound
from app.db.session import get_db
from app.rbac.engine import Principal
from app.rbac.scope import has_self_attrs
from app.resources import crud
from app.resources.registry import build_registry
from app.resources.spec import BY_PATH, REGISTRY, ResourceSpec

router = APIRouter(tags=["meta"])


def _can(spec: ResourceSpec, p: Principal, action: str) -> bool:
    if spec.public_read and action == "READ":
        return True
    return p.is_superuser or p.can(spec.perm_module, spec.perm_resource, action)


def _summary(spec: ResourceSpec, p: Principal) -> dict:
    write = not spec.read_only
    return {
        "path": spec.path, "table": spec.table, "title": spec.title, "module": spec.module_slug,
        "permission_module": spec.perm_module, "label_columns": spec.label_cols, "list_columns": spec.list_cols,
        "status_column": spec.status_col, "read_only": spec.read_only, "searchable": bool(spec.search),
        "can": {"read": _can(spec, p, "READ"), "create": write and _can(spec, p, "CREATE"),
                "update": write and _can(spec, p, "UPDATE"),
                "delete": write and not spec.no_delete and _can(spec, p, "DELETE"), "export": _can(spec, p, "EXPORT")},
        "actions": [{"name": t.name, "label": t.label, "from": list(t.from_states), "to": t.to_state,
                     "remarks": t.remarks, "danger": t.danger} for t in spec.transitions.values()
                    if p.is_superuser or p.can(spec.perm_module, spec.perm_resource, t.action)],
    }


def _detail(spec: ResourceSpec, p: Principal) -> dict:
    d = _summary(spec, p)
    d["primary_key"] = spec.pk
    d["columns"] = [{
        "name": c.name, "label": c.label, "kind": c.kind, "required": c.required, "nullable": c.nullable,
        "readonly": c.readonly or spec.read_only, "max_length": c.max_length, "choices": c.choices, "primary": c.pk,
        "references": (lambda t: {"path": t.path, "title": t.title} if t else None)(REGISTRY.get(c.fk_table))
        if c.fk_table else None,
    } for c in spec.columns.values() if not c.hidden]
    return d


def _listed(spec: ResourceSpec, p: Principal) -> bool:
    """A page appears in navigation only when the role holds a real grant for it. Reference tables (everybody can read
    them for dropdowns) are shown as pages only to people who may maintain them."""
    if p.is_superuser:
        return True
    if spec.perm_module == "IAM":
        return False            # accounts and access are managed from the Administration pages
    if not p.can(spec.perm_module, spec.perm_resource, "READ"):
        return False
    if spec.perm_module == "REFERENCE":
        return p.can(spec.perm_module, spec.perm_resource, "UPDATE") or p.can(spec.perm_module, spec.perm_resource, "CREATE")
    scope = p.scope_for(spec.perm_module, spec.perm_resource, "READ")
    if not scope.organisational:      # own-records only: show the page just when it can hold the person's own rows
        return has_self_attrs(spec.model)
    return True


@router.get("/meta")
def meta(principal: Principal = Depends(active_principal)):
    """Navigation tree and permissions for the signed-in user (resources they cannot read are omitted)."""
    build_registry()
    groups: dict[str, list[dict]] = {}
    for spec in REGISTRY.values():
        # Navigation lists only what the role was actually granted; world-readable reference data stays reachable
        # for form pickers through /lookups but never appears as a page the person did not get access to.
        if _listed(spec, principal):
            groups.setdefault(spec.group, []).append(_summary(spec, principal))
    ordered = [{"title": g, "resources": sorted(rs, key=lambda r: r["title"])} for g, rs in sorted(groups.items())]
    return {"groups": ordered}


@router.get("/meta/{module}/{slug}")
def meta_resource(module: str, slug: str, principal: Principal = Depends(active_principal)):
    spec = BY_PATH.get(f"{module}/{slug}")
    if spec is None:
        raise NotFound("Unknown resource.")
    if not _can(spec, principal, "READ"):
        raise Forbidden()
    return _detail(spec, principal)


@router.get("/lookups/{module}/{slug}")
def lookups(module: str, slug: str, request: Request, q: str | None = Query(default=None, max_length=100),
            ids: str | None = Query(default=None, max_length=1000), limit: int = Query(default=20, ge=1, le=100),
            principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Id/label pairs for dropdowns, restricted to rows the caller can read."""
    spec = BY_PATH.get(f"{module}/{slug}")
    if spec is None:
        raise NotFound("Unknown resource.")
    query, _ = crud.scoped(spec, principal, "READ")
    t = spec.model.__table__
    label = t.c[spec.label_cols[0]] if spec.label_cols else t.c[spec.pk]
    query = select(t.c[spec.pk], label).select_from(query.subquery()) if False else query
    pk = t.c[spec.pk]
    stmt = query.with_only_columns(pk, label)
    if ids:
        wanted = [int(i) if spec.columns[spec.pk].kind == "int" else i for i in ids.split(",") if (i.strip().isdigit() if spec.columns[spec.pk].kind == "int" else i.strip().isalnum())]
        stmt = stmt.where(pk.in_(wanted[:100]))
    if q:
        esc = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(label.ilike(f"%{esc}%", escape="\\"))
    rows = db.execute(stmt.order_by(label).limit(limit)).all()
    return {"results": [{"id": r[0], "label": str(r[1])} for r in rows]}
