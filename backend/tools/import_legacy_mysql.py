"""One-off importer: copy data from the legacy Django/MySQL SIMS database into the new PostgreSQL schema.

    uv run --with pymysql python -m tools.import_legacy_mysql \
        --mysql "mysql+pymysql://root:PASSWORD@127.0.0.1:3307/sims_reference_dev"

* Existing password hashes are kept (Django PBKDF2 is verified at login and upgraded to Argon2id on first use).
* Tables that no longer exist (Django internals, per-module audit/outbox tables) are skipped.
* The target database must already be migrated (``alembic upgrade head``) and empty.
"""
import argparse
import json
import sys
from datetime import UTC, datetime

import sqlalchemy as sa

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import make_engine

RENAMED = {
    "platform_institution_membership": "user_institution",
    "platform_institution_module": "institution_module",
    "platform_people_account_link": "person_account_link",
    "platform_people_invitation": "account_invitation",
    "platform_admission_fee_clearance": "admission_fee_clearance",
    "platform_consultancy_milestone": "consultancy_milestone",
    "platform_consultancy_receipt": "consultancy_receipt",
    "platform_consultancy_receipt_void": "consultancy_receipt_void",
    "platform_consultancy_team": "consultancy_team_member",
    "platform_evidence_expiry_notice": "evidence_expiry_notice",
    "platform_research_utilization_void": "research_utilization_void",
    "platform_staff_activity_attachment": "staff_activity_attachment",
    "platform_m8_availability": "timetable_availability",
    "platform_m8_exception": "timetable_exception",
    "platform_m8_occurrence": "timetable_occurrence",
    "platform_m8_plan": "timetable_plan",
    "platform_m8_policy": "timetable_policy",
    "platform_m8_revision": "timetable_revision",
    "platform_m8_solver_job": "timetable_solver_job",
    "platform_m8_workload_override": "timetable_workload_override",
    "platform_m9_policy": "attendance_policy",
    "platform_m9_coverage": "lesson_coverage",
    "platform_m9_lesson_revision": "lesson_plan_revision",
    "platform_m10_policy": "assessment_policy",
    "platform_m10_publication": "result_publication",
    "platform_m11_ledger": "feedback_ledger",
    "platform_registration_policy": "registration_policy",
    "platform_registration_progression": "registration_progression",
}
SKIP_COLUMNS = {("user_role_assignment", "scope_entity_id")}


def convert(value, col):
    if value is None:
        return None
    t = col.type
    if isinstance(t, sa.Boolean):
        return bool(value)
    if isinstance(t, sa.DateTime):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(t, sa.JSON) or t.__class__.__name__ == "JSONB":
        return json.loads(value) if isinstance(value, (str, bytes)) else value
    if isinstance(t, sa.String) and isinstance(value, bytes):
        return value.decode()
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mysql", required=True)
    args = ap.parse_args()
    src = sa.create_engine(args.mysql)
    dst = make_engine()
    src_tables = set(sa.inspect(src).get_table_names())
    inverse = {v: k for k, v in RENAMED.items()}
    report: dict[str, int] = {}
    with dst.begin() as out, src.connect() as inp:
        if out.execute(sa.text("select count(*) from user_account")).scalar():
            print("Target database is not empty; refusing to import.")
            return 1
        for table in Base.metadata.sorted_tables:
            name = table.name
            src_name = inverse.get(name, name)
            if src_name not in src_tables:
                continue
            rows = inp.execute(sa.text(f"select * from `{src_name}`")).mappings().all()
            if not rows:
                continue
            batch = []
            for r in rows:
                rec = {}
                for k, v in r.items():
                    if name == "user_account":
                        k = {"password": "password_hash", "date_joined": "created_at"}.get(k, k)
                        if k in ("is_staff", "last_login"):
                            continue
                    if k not in table.c or (name, k) in SKIP_COLUMNS:
                        continue
                    rec[k] = convert(v, table.c[k])
                if name == "user_account":
                    rec.setdefault("created_at", datetime.now(UTC))
                batch.append(rec)
            for i in range(0, len(batch), 500):
                out.execute(table.insert(), batch[i:i + 500])
            report[name] = len(batch)
        # keep identity/serial sequences ahead of imported ids
        for table in Base.metadata.sorted_tables:
            for col in table.primary_key.columns:
                if isinstance(col.type, (sa.Integer, sa.BigInteger, sa.SmallInteger)) and col.autoincrement is True:
                    out.execute(sa.text(
                        f"select setval(pg_get_serial_sequence('{table.name}', '{col.name}'), "
                        f"greatest((select coalesce(max({col.name}), 0) from {table.name}), 1))"))
    for k, v in sorted(report.items()):
        print(f"{k:45s} {v}")
    print(f"Imported {sum(report.values())} rows into {len(report)} tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
