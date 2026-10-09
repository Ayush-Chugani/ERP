"""Append-only audit trail and status history writers."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform import AuditLog, StatusHistory
from app.rbac.engine import Principal


def jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    return value


def diff(before: dict | None, after: dict | None) -> tuple[dict | None, dict | None]:
    """Keep only the keys that changed so the trail stays small and readable."""
    if before is None or after is None:
        return before, after
    keys = [k for k in after if before.get(k) != after.get(k)]
    return {k: before.get(k) for k in keys}, {k: after.get(k) for k in keys}


def record(db: Session, principal: Principal | None, *, action: str, module: str, resource: str,
           record_id: Any = None, before: dict | None = None, after: dict | None = None, reason: str | None = None,
           request_id: str | None = None, ip: str | None = None, institution_id: int | None = None) -> None:
    db.add(AuditLog(
        actor_user_id=principal.user_id if principal else None, action=action, module=module, resource=resource,
        record_id=None if record_id is None else str(record_id), before=jsonable(before), after=jsonable(after),
        reason=(reason or None) and reason[:500], request_id=request_id, ip_address=ip, institution_id=institution_id))


def status_change(db: Session, principal: Principal | None, entity: str, entity_id: Any, from_status: str | None,
                  to_status: str, action: str | None = None, remarks: str | None = None) -> None:
    db.add(StatusHistory(entity_type=entity, entity_id=str(entity_id), from_status=from_status, to_status=to_status,
                         action=action, changed_by_id=principal.user_id if principal else None,
                         remarks=(remarks or None) and remarks[:1000]))
