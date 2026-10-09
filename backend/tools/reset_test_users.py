"""Reset every login to a clean, easy-to-test set: one account per role, all with the same password.

TESTING ONLY. It deletes all users except the `admin` row (which is kept so records that point at it stay valid, and which
becomes the super administrator), re-points every "created by / updated by" reference to `admin`, then recreates the role
accounts (admin, orgadmin, registrar, ... see app.seed.demo.PERSONAS) with the given password. The password bypasses the
password policy on purpose, so it can be short. Never run this on a real installation.

    uv run python -m tools.reset_test_users --password 'admin@123' --yes
"""
import argparse
import sys

import sqlalchemy as sa

from app.config import get_settings
from app.core.security import hash_password
from app.db.session import db_session
from app.rbac import catalogue
from app.seed.demo import PERSONAS

# username, role, scope, person kind (links are kept from the existing accounts when they exist)
BASE = [
    ("orgadmin", "INSTITUTION_ADMIN", "INSTITUTION", None), ("registrar", "REGISTRAR", "INSTITUTION", None),
    ("campusadm", "CAMPUS_DIRECTOR", "CAMPUS", None), ("hod", "HEAD_DEPARTMENT", "DEPARTMENT", "employee"),
    ("teacher", "FACULTY", "DEPARTMENT", "employee"), ("examcell", "CONTROLLER_EXAMINATIONS", "INSTITUTION", None),
    ("support", "GRIEVANCE_OFFICER", "INSTITUTION", None), ("student", "STUDENT", "SELF", "student"),
    ("student2", "STUDENT", "SELF", "student"),
]
IMMUTABLE = ["audit_log", "status_history", "evidence_document_audit", "consultancy_receipt", "consultancy_receipt_void",
             "research_utilization_void"]
# user-owned rows removed together with the user (everything else is re-pointed to the kept admin)
DELETE_WITH_USER = {"person_account_link", "user_role_assignment", "password_history", "user_institution",
                    "user_permission_override", "role_delegation", "account_invitation", "announcement_user_target",
                    "auth_session", "notification"}


def run(password: str) -> None:
    with db_session() as db:
        admin = db.execute(sa.text("SELECT user_id FROM user_account WHERE lower(username) = 'admin'")).scalar()
        if admin is None:
            raise SystemExit("There is no `admin` user to keep; run `python -m app.cli create-admin` first.")
        snapshot = {u: (s, e, inst, scope_col) for u, s, e, inst, scope_col in db.execute(sa.text(
            "SELECT u.username, l.student_id, l.employee_id, u.institution_id, "
            "(SELECT a.scope_type || ':' || COALESCE(a.institution_id, a.campus_id, a.department_id, a.programme_id)::text "
            " FROM user_role_assignment a WHERE a.user_id = u.user_id AND a.assignment_status = 'ACTIVE' AND a.scope_type NOT IN ('SELF','GLOBAL') LIMIT 1) "
            "FROM user_account u LEFT JOIN person_account_link l ON l.user_id = u.user_id"))}
        inst = db.execute(sa.text("SELECT institution_id FROM institution ORDER BY 1 LIMIT 1")).scalar()
        others = [u for (u,) in db.execute(sa.text("SELECT user_id FROM user_account WHERE user_id <> :a"), {"a": admin})]
        refs = db.execute(sa.text(
            "SELECT c.conrelid::regclass::text, a.attname FROM pg_constraint c JOIN pg_attribute a "
            "ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) WHERE c.contype = 'f' AND c.confrelid = 'user_account'::regclass")).all()
        for table in IMMUTABLE:
            db.execute(sa.text(f'ALTER TABLE "{table}" DISABLE TRIGGER USER'))  # noqa: S608
        if others:
            for table, col in refs:
                if table in DELETE_WITH_USER or table == "user_account":
                    db.execute(sa.text(f'DELETE FROM "{table}" WHERE "{col}" = ANY(:o)'), {"o": others})  # noqa: S608
                else:
                    db.execute(sa.text(f'UPDATE "{table}" SET "{col}" = :a WHERE "{col}" = ANY(:o)'), {"a": admin, "o": others})  # noqa: S608
            db.execute(sa.text("UPDATE login_audit SET user_id = NULL WHERE user_id = ANY(:o)"), {"o": others})
            db.execute(sa.text("DELETE FROM user_account WHERE user_id = ANY(:o)"), {"o": others})
        for table in IMMUTABLE:
            db.execute(sa.text(f'ALTER TABLE "{table}" ENABLE TRIGGER USER'))  # noqa: S608
        # the kept administrator: super admin, known password, clean state
        db.execute(sa.text("DELETE FROM user_role_assignment WHERE user_id = :a"), {"a": admin})
        db.execute(sa.text("DELETE FROM person_account_link WHERE user_id = :a"), {"a": admin})
        db.execute(sa.text(
            "UPDATE user_account SET password_hash = :h, is_superuser = true, is_active = true, account_status = 'ACTIVE', "
            "must_change_password = false, multi_factor_enabled = false, mfa_secret = NULL, failed_login_count = 0, "
            "locked_until = NULL, institution_id = NULL, email = 'admin@example.org', security_version = security_version + 1 "
            "WHERE user_id = :a"), {"h": hash_password(password), "a": admin})
        db.execute(sa.text("INSERT INTO user_role_assignment (user_id, role_id, scope_type, valid_from, assignment_status) "
                           "SELECT :a, role_id, 'GLOBAL', now(), 'ACTIVE' FROM role WHERE role_code = 'SUPER_ADMIN'"), {"a": admin})
        try:
            db.execute(sa.text("DELETE FROM rate_limit_bucket"))
        except sa.exc.DBAPIError:
            pass
        _create_accounts(db, snapshot, inst, password)
        catalogue.sync(db)


def _create_accounts(db, snapshot, inst, password) -> None:
    pw = hash_password(password)
    dept = db.execute(sa.text("SELECT department_id FROM department ORDER BY 1 LIMIT 1")).scalar()
    campus = db.execute(sa.text("SELECT campus_id FROM campus ORDER BY 1 LIMIT 1")).scalar()
    programme = db.execute(sa.text("SELECT programme_id FROM programme WHERE department_id = :d ORDER BY 1 LIMIT 1"), {"d": dept}).scalar()
    for username, role, scope, _person in [*BASE, *PERSONAS]:
        student, employee, owned, held = snapshot.get(username, (None, None, None, None))
        col, val = {"INSTITUTION": ("institution_id", inst), "CAMPUS": ("campus_id", campus),
                    "DEPARTMENT": ("department_id", dept), "PROGRAMME": ("programme_id", programme)}.get(scope, (None, None))
        if held:                                              # keep the scope the old account really had
            kind, _, ident = held.partition(":")
            col = {"INSTITUTION": "institution_id", "CAMPUS": "campus_id", "DEPARTMENT": "department_id", "PROGRAMME": "programme_id"}[kind]
            val = int(ident)
        uid = db.execute(sa.text(
            "INSERT INTO user_account (username, email, first_name, last_name, password_hash, is_active, account_status, "
            "must_change_password, institution_id) VALUES (:u, :e, :f, 'Test', :h, true, 'ACTIVE', false, :i) RETURNING user_id"),
            {"u": username, "e": f"{username}@example.org", "f": role.replace("_", " ").title(), "h": pw,
             "i": None if scope == "GLOBAL" else inst}).scalar()
        db.execute(sa.text(
            f"INSERT INTO user_role_assignment (user_id, role_id, scope_type, {col or 'institution_id'}, valid_from, assignment_status) "  # noqa: S608
            "SELECT :u, role_id, :s, :v, now(), 'ACTIVE' FROM role WHERE role_code = :r"),
            {"u": uid, "s": scope, "v": val if col else None, "r": role})
        for kind, pid in (("student_id", student), ("employee_id", employee)):
            if pid:
                db.execute(sa.text(f"INSERT INTO person_account_link ({kind}, user_id) VALUES (:p, :u)"), {"p": pid, "u": uid})  # noqa: S608
        if employee:
            catalogue.ensure_staff_self(db, uid)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--password", required=True)
    ap.add_argument("--yes", action="store_true", help="confirm that every user except `admin` will be deleted")
    args = ap.parse_args(argv)
    if get_settings().env == "production":
        raise SystemExit("Refusing to run with SIMS_ENV=production.")
    if not args.yes:
        raise SystemExit("Pass --yes to confirm: all users except `admin` are deleted and recreated.")
    run(args.password)
    print("Users reset: admin (super administrator) and one account per role, all with the given password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
