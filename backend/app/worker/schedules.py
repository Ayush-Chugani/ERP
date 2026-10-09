from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.platform import JobSchedule

SCHEDULES = [
    ("maintenance.purge", "maintenance.purge", 3600, {}),
    ("memberships.expire", "memberships.expire", 86400, {}),
    ("evidence.expiry_scan", "evidence.expiry_scan", 86400, {}),
    ("documents.expire", "documents.expire", 86400, {}),
]


def ensure_schedules(db: Session) -> None:
    for sid, kind, interval, payload in SCHEDULES:
        stmt = insert(JobSchedule).values(schedule_id=sid, kind=kind, interval_seconds=interval, payload=payload)
        db.execute(stmt.on_conflict_do_update(index_elements=["schedule_id"],
                                              set_={"kind": kind, "interval_seconds": interval}))
