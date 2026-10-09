"""Operations CLI:  uv run python -m app.cli <command>

    migrate                    apply database migrations
    bootstrap                  sync permission catalogue / roles / schedules (safe to repeat)
    create-admin               create or reset a super administrator (password from SIMS_BOOTSTRAP_ADMIN_PASSWORD
                               or an interactive prompt)
    seed-content               fill every section with sample rows for the demo personas (repeatable)
    seed-demo                  load the demo campus (students, staff, timetable, …) and demo personas
    worker                     run the background job worker
"""
import argparse
import getpass
import sys

from sqlalchemy import select


def cmd_migrate(_: argparse.Namespace) -> int:
    from alembic.config import Config

    from alembic import command

    command.upgrade(Config("alembic.ini"), "head")
    return 0


def cmd_bootstrap(_: argparse.Namespace) -> int:
    import app.models  # noqa: F401
    from app.db.session import db_session
    from app.rbac import catalogue
    from app.seed import loader
    from app.worker.schedules import ensure_schedules

    with db_session() as db:
        loader.load(db, "base", only_if_empty=True)
        stats = catalogue.sync(db)
        ensure_schedules(db)
    print("Catalogue synced:", stats)
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    import app.models  # noqa: F401
    from app.config import get_settings
    from app.core.security import hash_password
    from app.db.session import db_session
    from app.models.accounts import UserAccount
    from app.services.auth import validate_password

    s = get_settings()
    username = args.username or s.bootstrap_admin_username or input("Username: ").strip()
    email = args.email or s.bootstrap_admin_email or f"{username}@example.invalid"
    password = s.bootstrap_admin_password or getpass.getpass("Password: ")
    validate_password(password)
    with db_session() as db:
        user = db.scalar(select(UserAccount).where(UserAccount.username == username))
        if user is None:
            user = UserAccount(username=username, email=email, password_hash=hash_password(password),
                               is_superuser=True, account_status="ACTIVE", is_active=True)
            db.add(user)
            print(f"Created super administrator '{username}'.")
        elif args.reset:
            user.password_hash = hash_password(password)
            user.is_superuser = True
            user.security_version += 1
            print(f"Reset password for '{username}'.")
        else:
            print(f"'{username}' already exists; pass --reset to change the password.")
    return 0


def cmd_seed_demo(args: argparse.Namespace) -> int:
    from app.seed.demo import load_demo

    load_demo(force=args.force)
    return 0


def cmd_seed_content(_: argparse.Namespace) -> int:
    from app.seed.demo import ensure_demo_content

    added = ensure_demo_content()
    print(f"Demo content ready ({sum(added.values())} rows added across {len(added)} tables).")
    return 0


def cmd_worker(_: argparse.Namespace) -> int:
    from app.worker.runner import run_forever

    run_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sims")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    sub.add_parser("bootstrap").set_defaults(fn=cmd_bootstrap)
    a = sub.add_parser("create-admin")
    a.add_argument("--username")
    a.add_argument("--email")
    a.add_argument("--reset", action="store_true")
    a.set_defaults(fn=cmd_create_admin)
    d = sub.add_parser("seed-demo")
    d.add_argument("--force", action="store_true", help="load even if the database already has people")
    d.set_defaults(fn=cmd_seed_demo)
    sub.add_parser("seed-content").set_defaults(fn=cmd_seed_content)
    sub.add_parser("worker").set_defaults(fn=cmd_worker)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
