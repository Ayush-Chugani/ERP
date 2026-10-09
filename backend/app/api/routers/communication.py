"""Announcement audiences: custom recipients and programme targets (editable until the announcement is approved)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import active_principal
from app.core.errors import Conflict
from app.db.session import get_db
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry

router = APIRouter(prefix="/communication", tags=["Communication"])


class TargetsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_ids: list[int] = Field(default_factory=list, max_length=5000)
    programme_ids: list[int] = Field(default_factory=list, max_length=500)


@router.get("/announcement/{announcement_id}/targets")
def get_targets(announcement_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    crud.get_one(db, build_registry()["announcement"], principal, announcement_id)
    users = [u for (u,) in db.execute(text("SELECT user_id FROM announcement_user_target WHERE announcement_id = :a ORDER BY 1"),
                                      {"a": announcement_id})]
    progs = [p for (p,) in db.execute(text("SELECT programme_id FROM announcement_programme_target WHERE announcement_id = :a ORDER BY 1"),
                                      {"a": announcement_id})]
    return {"user_ids": users, "programme_ids": progs}


@router.put("/announcement/{announcement_id}/targets")
def set_targets(announcement_id: int, body: TargetsIn, principal: Principal = Depends(active_principal),
                db: Session = Depends(get_db)):
    ann = crud.get_one(db, build_registry()["announcement"], principal, announcement_id, "UPDATE", lock=True)
    if ann.approval_status not in ("DRAFT", "REJECTED"):
        raise Conflict("Audiences can only be changed while the announcement is a draft or rejected.", code="record_locked")
    db.execute(text("DELETE FROM announcement_user_target WHERE announcement_id = :a"), {"a": announcement_id})
    db.execute(text("DELETE FROM announcement_programme_target WHERE announcement_id = :a"), {"a": announcement_id})
    for uid in dict.fromkeys(body.user_ids):
        db.execute(text("INSERT INTO announcement_user_target (announcement_id, user_id) SELECT :a, user_id FROM user_account "
                        "WHERE user_id = :u"), {"a": announcement_id, "u": uid})
    for pid in dict.fromkeys(body.programme_ids):
        db.execute(text("INSERT INTO announcement_programme_target (announcement_id, programme_id) SELECT :a, programme_id "
                        "FROM programme WHERE programme_id = :p"), {"a": announcement_id, "p": pid})
    db.commit()
    return get_targets(announcement_id, principal, db)
