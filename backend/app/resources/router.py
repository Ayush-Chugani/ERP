"""Mount generic REST routes for every registered resource.

    GET    /{module}/{resource}                  list (filters, search, ordering, pagination)
    POST   /{module}/{resource}                  create
    GET    /{module}/{resource}/export           CSV export
    GET    /{module}/{resource}/{id}             retrieve (+ available workflow actions)
    PATCH  /{module}/{resource}/{id}             partial update (optimistic concurrency via ``version``)
    DELETE /{module}/{resource}/{id}             delete (soft where the table supports it)
    POST   /{module}/{resource}/{id}/actions/{name}   workflow transition
"""
import hashlib
import json
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import active_principal, client_ip
from app.core.errors import Conflict
from app.db.session import get_db
from app.models.accounts import UserAccount
from app.models.platform import IdempotencyKey, StatusHistory
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry
from app.resources.spec import ResourceSpec


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str | None = Field(default=None, max_length=1000)


def ctx(request: Request) -> dict:
    return {"request_id": getattr(request.state, "request_id", None), "ip": client_ip(request)}


def _idem(db: Session, principal: Principal, request: Request, key: str | None, payload: Any):
    """Return a stored response for a repeated Idempotency-Key, else the (key, digest) to store after success."""
    if not key:
        return None, None
    key = key[:120]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    row = db.get(IdempotencyKey, (key, principal.user_id))
    if row is not None:
        if row.request_digest != digest or row.route != request.url.path:
            raise Conflict("This Idempotency-Key was already used for a different request.", code="idempotency_conflict")
        if row.response_body is not None:
            return row.response_body, None
        raise Conflict("A request with this Idempotency-Key is still being processed.", code="idempotency_in_flight")
    return None, (key, digest)


def _store(db: Session, principal: Principal, request: Request, token, body: dict) -> None:
    if token:
        db.add(IdempotencyKey(key=token[0], user_id=principal.user_id, route=request.url.path,
                              request_digest=token[1], response_status=200, response_body=body))


def build_router(spec: ResourceSpec) -> APIRouter:
    router = APIRouter(prefix=f"/{spec.module_slug}/{spec.slug}", tags=[spec.group])
    Create, Update, Out = spec.create_model, spec.update_model, spec.out_model
    OutL = create_model(f"{Out.__name__}L", __base__=Out, labels=(dict[str, str], Field(default_factory=dict)),
                        actions=(list[dict], Field(default_factory=list)),
                        workflow_status=(str | None, None))
    Page = create_model(f"{Out.__name__}Page", count=(int, ...), page=(int, ...), page_size=(int, ...),
                        next=(int | None, None), previous=(int | None, None), results=(list[OutL], ...))
    simple_pk = len(spec.model.__table__.primary_key.columns) == 1
    pk_type = {"int": int, "string": str}.get(spec.columns[spec.pk].kind, str)
    name = spec.table

    @router.get("", response_model=Page, name=f"list_{name}")
    def list_(request: Request, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
        return crud.list_rows(db, spec, principal, request.query_params)

    @router.get("/export", response_class=Response, name=f"export_{name}")
    def export(request: Request, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
        text = crud.export_csv(db, spec, principal, request.query_params)
        crud.audit.record(db, principal, action="export", module=spec.perm_module, resource=spec.table,
                          request_id=ctx(request)["request_id"], ip=ctx(request)["ip"])
        db.commit()
        return Response(text, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{spec.table}.csv"'})

    if spec.read_only and not simple_pk:
        return router

    if not spec.read_only:
        @router.post("", response_model=OutL, status_code=201, name=f"create_{name}")
        def create(request: Request, body: Create, principal: Principal = Depends(active_principal),  # type: ignore[valid-type]
                   db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
            replay, token = _idem(db, principal, request, idempotency_key, body.model_dump(mode="json"))
            if replay is not None:
                return replay
            obj = crud.create_row(db, spec, principal, body, ctx(request))
            result = crud.detail(db, spec, obj)
            result["actions"] = crud.allowed_actions(db, spec, principal, obj)
            _store(db, principal, request, token, OutL.model_validate(result).model_dump(mode="json"))
            db.commit()
            return result

    @router.get("/{pk}", response_model=OutL, name=f"get_{name}")
    def retrieve(pk: pk_type, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):  # type: ignore[valid-type]
        obj = crud.get_one(db, spec, principal, pk)
        result = crud.detail(db, spec, obj)
        result["actions"] = crud.allowed_actions(db, spec, principal, obj)
        return result

    @router.get("/{pk}/history", name=f"history_{name}")
    def history(pk: pk_type, principal: Principal = Depends(active_principal),  # type: ignore[valid-type]
                db: Session = Depends(get_db)):
        """Workflow trail for one record (visible to anyone who can read the record)."""
        crud.get_one(db, spec, principal, pk)
        rows = db.execute(select(StatusHistory, UserAccount.username).outerjoin(
            UserAccount, UserAccount.user_id == StatusHistory.changed_by_id).where(
            StatusHistory.entity_type == spec.table, StatusHistory.entity_id == str(pk)).order_by(
            StatusHistory.status_history_id)).all()
        return {"results": [{"from_status": h.from_status, "to_status": h.to_status, "action": h.action,
                             "changed_at": h.changed_at, "changed_by": who, "remarks": h.remarks} for h, who in rows]}

    if not spec.read_only:
        @router.patch("/{pk}", response_model=OutL, name=f"update_{name}")
        def update(request: Request, pk: pk_type, body: Update,  # type: ignore[valid-type]
                   principal: Principal = Depends(active_principal), db: Session = Depends(get_db),
                   if_match: str | None = Header(default=None)):
            if if_match and spec.versioned and "version" not in body.model_fields_set:
                try:
                    body.version = int(if_match.strip('"W/'))
                    body.model_fields_set.add("version")
                except ValueError:
                    pass
            obj = crud.update_row(db, spec, principal, pk, body, ctx(request))
            result = crud.detail(db, spec, obj)
            result["actions"] = crud.allowed_actions(db, spec, principal, obj)
            db.commit()
            return result

        if not spec.no_delete:
            @router.delete("/{pk}", status_code=204, name=f"delete_{name}")
            def delete(request: Request, pk: pk_type, principal: Principal = Depends(active_principal),  # type: ignore[valid-type]
                       db: Session = Depends(get_db)):
                crud.delete_row(db, spec, principal, pk, ctx(request))
                db.commit()
                return Response(status_code=204)

    if spec.transitions:
        @router.post("/{pk}/actions/{action_name}", response_model=OutL, name=f"action_{name}")
        def action(request: Request, pk: pk_type, action_name: str, body: ActionIn = Body(default_factory=ActionIn),  # type: ignore[valid-type]
                   principal: Principal = Depends(active_principal), db: Session = Depends(get_db),
                   idempotency_key: str | None = Header(default=None)):
            replay, token = _idem(db, principal, request, idempotency_key, {"pk": str(pk), "a": action_name,
                                                                             "r": body.remarks})
            if replay is not None:
                return replay
            obj = crud.run_transition(db, spec, principal, pk, action_name, body.remarks, ctx(request))
            result = crud.detail(db, spec, obj)
            result["actions"] = crud.allowed_actions(db, spec, principal, obj)
            _store(db, principal, request, token, OutL.model_validate(result).model_dump(mode="json"))
            db.commit()
            return result

    return router


def resource_routers() -> list[APIRouter]:
    return [build_router(s) for s in build_registry().values()]
