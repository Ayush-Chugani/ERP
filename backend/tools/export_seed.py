"""Developer tool: snapshot the current database into the packaged seed fixtures.

    SIMS_DATABASE_URL=<source db> uv run python -m tools.export_seed

Writes app/seed/data/base.json.gz (permission catalogue, roles, reference lookups; needed in every environment) and
app/seed/data/demo.json.gz (sample campus data). Password hashes, sessions and audit rows are never exported.
"""
import gzip
import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import make_engine

OUT = Path(__file__).resolve().parents[1] / "app" / "seed" / "data"
BASE_TABLES = {
    "access_action", "access_module", "access_resource", "permission", "role", "role_permission",
    "activity_type", "admission_category", "announcement_type", "approval_status", "attendance_status", "award_category",
    "blood_group", "certificate_type", "confidentiality_level", "conference_contribution_type", "country",
    "course_category", "designation", "document_type", "employment_source", "event_mode", "gender",
    "grievance_category", "membership_type", "participation_level", "professional_contribution_type", "religion",
    "research_status", "social_category", "staff_category", "staff_type", "state", "verification_status",
    "feedback_question_category", "evidence_type", "funding_type",
}
SKIP = {"auth_session", "login_audit", "password_history", "rate_limit_bucket", "idempotency_key", "job",
        "job_schedule", "audit_log", "status_history", "notification", "alembic_version", "account_invitation"}


def enc(v):
    if isinstance(v, (datetime, date, time)):
        return {"$t": v.isoformat()}
    if isinstance(v, Decimal):
        return {"$d": str(v)}
    return v


def base_closure() -> set[str]:
    """A table may only be 'base' if everything it references is base too (otherwise the fixture would not load)."""
    base = set(BASE_TABLES)
    changed = True
    while changed:
        changed = False
        for t in Base.metadata.sorted_tables:
            if t.name in base and any(fk.column.table.name not in base and fk.column.table.name != t.name
                                      for fk in t.foreign_keys):
                base.discard(t.name)
                changed = True
    return base


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_names = base_closure()
    eng = make_engine()
    base: dict[str, list] = {}
    demo: dict[str, list] = {}
    with eng.connect() as c:
        for t in Base.metadata.sorted_tables:
            if t.name in SKIP:
                continue
            cols = [col for col in t.columns if col.computed is None]
            rows = []
            for r in c.execute(sa.select(*cols)).mappings():
                rec = {k: enc(v) for k, v in r.items()}
                if t.name == "user_account":
                    rec["password_hash"] = "!"
                    rec["mfa_secret"] = None
                    rec["multi_factor_enabled"] = False
                    rec["failed_login_count"] = 0
                    rec["locked_until"] = None
                    if rec["user_id"] == 1:
                        rec["username"] = "demoadmin"
                rows.append(rec)
            if rows:
                (base if t.name in base_names else demo)[t.name] = rows
    for name, data in (("base", base), ("demo", demo)):
        with gzip.open(OUT / f"{name}.json.gz", "wt", encoding="utf8") as f:
            json.dump(data, f, separators=(",", ":"))
        print(name, {k: len(v) for k, v in data.items()}.__len__(), "tables", sum(len(v) for v in data.values()), "rows")


if __name__ == "__main__":
    main()
